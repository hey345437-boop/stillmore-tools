# Analysis contract

`analysis.json` has `schema_version: 1`, the exact `run_id` from the scan, and `items`.

Each item:

```json
{
  "video_id": "original platform video ID",
  "source_url": "exact URL from scan",
  "historical_demo": false,
  "review_status": "reviewed",
  "review_method": "Browser playback and sampled frames across the full duration; audio not verified",
  "evidence": [{"at_seconds": 0, "observation": "What is visibly present"}],
  "hook": "Observed opening device",
  "mechanism_hypothesis": "Why this might attract attention; not a causal claim",
  "limits": "What the metric/observation cannot establish",
  "adaptation": {
    "merchant": "Suitable business",
    "concept": "Original adaptation",
    "assets": ["Real product", "Phone and tripod"],
    "duration_seconds": 15,
    "format": "9:16",
    "cta": "A concrete next action",
    "qc": ["Check visible product details against the actual offer"]
  },
  "shots": [
    {"start": 0, "end": 3, "visual": "Camera position and observable action", "copy": "Original on-screen copy", "audio": "Sound or edit instruction"},
    {"start": 3, "end": 15, "visual": "Next action", "copy": "Original ending", "audio": "Hold for readability"}
  ]
}
```

`review_status: unavailable` instead needs a non-empty `reason`, and must not contain invented hooks or shots. Every ID in `scan.selected_ids` needs one reviewed or unavailable entry. A historical demo must refer to a real video in `scan.videos`, meet the runtime/view rules, and be explicitly labelled; it does not change the daily selection count.

Evidence observations must be specific to the reviewed source. Remake timings describe a new proposed film, not unseen original shots. Leave unverified dialogue/audio out of the observed-evidence claims. Describe suggested sound design only in the remake.
