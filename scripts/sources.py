"""Public YouTube feeds and RSS discovery; no account integrations."""
import re
import time
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from runtime_lookup import duration_index
CFG = {}

def fetch(url, attempts=2):
    for i in range(attempts):
        try:
            req = Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; Stillmore editorial feed reader)"})
            with urlopen(req, timeout=12) as res:
                return res.read(4_000_000)
        except OSError:
            if i + 1 == attempts:
                raise
            time.sleep(1)

def collect(spec):
    name, kind, url = spec
    try:
        raw = fetch(url)
        root = ET.fromstring(raw)
        rows = []
        if kind == "channel":
            if root.findtext("{*}channelId", "").removeprefix("UC") != CFG["channels"][name]["channel"][2:]:
                raise ValueError("Unexpected channel identity")
            for entry in root.findall("{*}entry"):
                metric = entry.find(".//{*}statistics")
                ident = entry.findtext("{*}videoId")
                if not ident or not re.fullmatch(r"[\w-]{11}", ident):
                    continue
                views = metric.get("views", "") if metric is not None else ""
                rows.append(dict(id=ident, source=name, sector=CFG["channels"][name]["sector"],
                    brand=entry.findtext("{*}author/{*}name"), title=entry.findtext("{*}title"),
                    published=entry.findtext("{*}published"), description=entry.findtext(".//{*}description", ""),
                    views=int(views) if views.isdigit() else None, url="https://www.youtube.com/watch?v="+ident))
        else:
            if root.find("channel") is None:
                raise ValueError("Expected RSS channel")
            for item in root.findall("./channel/item")[:35]:
                rows.append(dict(title=item.findtext("title"), url=item.findtext("link"), date=item.findtext("pubDate")))
        health = dict(source=name, kind=kind, url=url, ok=True, items=len(rows))
        if kind == "channel" and rows:
            channel = CFG["channels"][name]["channel"]
            link = "https://www.youtube.com/playlist?list=UU"+channel[2:]
            try:
                durations = duration_index(fetch(link))
                health["durations_found"] = sum(row["id"] in durations for row in rows)
            except (OSError, ValueError, KeyError) as err:
                durations = {}
                health["duration_error"] = str(err)
            for row in rows:
                row.update(duration_seconds=durations.get(row["id"]), duration_source=link)
        return health, rows, raw
    except (OSError, ValueError, ET.ParseError) as err:
        return dict(source=name, kind=kind, url=url, ok=False, error=str(err)), [], b""
