#!/usr/bin/env python3
"""Capture public evidence and prepare a daily research queue. Python 3.10+."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone, timedelta
import gzip
import hashlib
import json
from pathlib import Path
import sqlite3
from zoneinfo import ZoneInfo

import sources

ROOT = Path(__file__).resolve().parents[1]


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def eligible(row, now, config):
    reasons = []
    try:
        published = datetime.fromisoformat(row["published"].replace("Z", "+00:00"))
        age = (now - published).total_seconds() / 3600
        if not 0 <= age <= config["lookback_hours"]:
            reasons.append("outside_discovery_window")
    except (KeyError, ValueError, TypeError):
        age = None
        reasons.append("unverified_publish_time")
    duration, views = row.get("duration_seconds"), row.get("views")
    if type(duration) is not int or not 0 < duration < config["duration_under_seconds"]:
        reasons.append("runtime_unknown_or_outside_limit")
    if type(views) is not int or views <= config["minimum_views_exclusive"]:
        reasons.append("views_unknown_or_below_threshold")
    return reasons, age


def observation_delta(previous, now, views):
    if previous is None or type(views) is not int:
        return None
    at, prior = previous
    hours = (now - datetime.fromisoformat(at)).total_seconds() / 3600
    if hours <= 0:
        return None
    return {"since": at, "previous_views": prior, "views": views - prior,
            "interval_hours": round(hours, 4),
            "views_per_hour": round((views - prior) / hours, 1) if hours >= 1 else None,
            "negative_change": views < prior}


def scan(config_path, state, output):
    config = json.loads(config_path.read_text())
    sources.CFG = config
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%dT%H%M%S%fZ")
    destination = output or state / "runs" / run_id
    destination.mkdir(parents=True, exist_ok=True)
    if (destination / "scan.json").exists():
        raise ValueError("Output already contains a scan; choose a new --out directory")
    state.mkdir(parents=True, exist_ok=True)
    specs = [(name, "channel", "https://www.youtube.com/feeds/videos.xml?channel_id=" + row["channel"])
             for name, row in config["channels"].items()]
    specs += [(name, "discovery", url) for name, url in config["discovery"].items()]
    health, videos, leads = [], [], []
    with ThreadPoolExecutor(max_workers=8) as pool:
        batches = list(pool.map(sources.collect, specs))
    with sqlite3.connect(state / "observations.sqlite", timeout=45) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS observation (platform TEXT, video TEXT, at TEXT, views INTEGER, PRIMARY KEY(platform,video,at))")
        for status, rows, raw in batches:
            observed = datetime.now(timezone.utc)
            status["observed_at"] = observed.isoformat()
            health.append(status)
            if not status["ok"]:
                continue
            digest = hashlib.sha256(raw).hexdigest()
            relative = "evidence/" + digest + ".xml.gz"
            (destination / "evidence").mkdir(exist_ok=True)
            (destination / relative).write_bytes(gzip.compress(raw))
            status.update(snapshot_sha256=digest, evidence_file=relative)
            if status["kind"] == "discovery":
                leads.extend(dict(row, source=status["source"], evidence_file=relative,
                                  status="lead_only_original_video_not_verified") for row in rows)
                continue
            for row in rows:
                previous = conn.execute("SELECT at,views FROM observation WHERE platform='youtube' AND video=? AND views IS NOT NULL ORDER BY at DESC LIMIT 1", (row["id"],)).fetchone()
                conn.execute("INSERT INTO observation VALUES ('youtube',?,?,?)", (row["id"], observed.isoformat(), row["views"]))
                reasons, age = eligible(row, observed, config)
                videos.append(dict(row, platform="youtube", observed_at=observed.isoformat(),
                                   age_hours=round(age, 2) if age is not None else None,
                                   eligible=not reasons, exclusions=reasons,
                                   fresh_priority=age is not None and 0 <= age <= config["priority_hours"],
                                   evidence_file=relative, snapshot_sha256=digest,
                                   delta=observation_delta(previous, observed, row["views"])))
    # A video appearing in more than one source is one candidate, not several.
    unique = {(row["platform"], row["id"]): row for row in videos}
    candidates = sorted((row for row in unique.values() if row["eligible"]),
                        key=lambda row: (row["fresh_priority"], row["views"]), reverse=True)
    dedup_leads = {}
    for row in leads:
        key = row.get("url")
        if key and key not in dedup_leads:
            dedup_leads[key] = row
    successful_channels = sum(h["ok"] for h in health if h["kind"] == "channel")
    status = "candidates_found" if candidates else "no_qualifying_videos" if successful_channels else "coverage_insufficient"
    data = {"schema_version": 1, "run_id": run_id, "started_at": now.isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(), "timezone": config["timezone"],
            "status": status, "rules": {k: config[k] for k in ("lookback_hours", "priority_hours", "duration_under_seconds", "minimum_views_exclusive", "max_results")},
            "coverage": {"total_sources": len(health), "readable_sources": sum(h["ok"] for h in health),
                         "videos_observed": len(unique), "qualifying_videos": len(candidates)},
            "sources": health, "candidates": candidates,
            "selected_ids": [r["id"] for r in candidates[:config["max_results"]]],
            "videos": list(unique.values()), "discovery_leads": list(dedup_leads.values()),
            "limitations": ["YouTube public counts only; not unique reach, sales, retention or verified organic growth.",
                            "TikTok/Instagram RSS results are discovery leads, not platform video measurements.",
                            "Playback verification and creative analysis are performed by the host AI after this scan.",
                            "Only videos still present in the channel's feed can be re-observed; this is not a full watchlist API."]}
    write_json(destination / "scan.json", data)
    request = {"schema_version": 1, "run_id": run_id, "items": [{"video_id": r["id"], "source_url": r["url"],
              "status": "awaiting_video_review", "evidence": [], "hook": "", "mechanism_hypothesis": "",
              "limits": "", "adaptation": {}, "shots": []} for r in candidates[:config["max_results"]]]}
    write_json(destination / "analysis.request.json", request)
    print(json.dumps({"scan": str((destination / "scan.json").resolve()), "status": status,
                      "coverage": data["coverage"], "candidates": [{k:r[k] for k in ("id","title","brand","views","duration_seconds","age_hours","url")} for r in candidates]}, ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=ROOT / "sources.json")
    parser.add_argument("--state", type=Path, default=ROOT / "state")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args()
    scan(args.config, args.state, args.out)
