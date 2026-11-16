<div align="center">

# Stillmore Trend Scout

### Stop scrolling for inspiration. Start with a script.

**Give your AI a daily ecommerce video research job.**

Discover promising product videos. Break down the creative. Get an original script for your next shoot.

[Quick start](#quick-start) · [Example brief](docs/example-brief.md) · [Daily setup](references/scheduling.md) · [中文](README.zh-CN.md) · [Stillmore](https://stillmore.studio/)

**Open source · MIT · 46 configured sources · Python standard library**

</div>

---

Your next product video can start with more than a blank page.

Stillmore Trend Scout gives a tool-enabled AI a repeatable research workflow: find recent short product videos, check the public evidence, watch the originals, and turn creative observations into shot-by-shot remake scripts using **your own product and assets**.

Run it once for a creative research session. Schedule the complete workflow in a compatible AI host for a daily brief.

```text
28 YouTube channels + 18 RSS discovery feeds
                    ↓
      Recent videos + verified public metrics
                    ↓
        Your AI watches and breaks them down
                    ↓
 Original links → creative insights → scripts you can shoot
```

## What lands in your brief

| Deliverable | What you get |
| --- | --- |
| Original video | Direct link, publisher, publication time, runtime and observed views |
| Creative breakdown | Opening hook, timestamped observations and a hypothesis about the creative appeal |
| Your remake | Suitable merchant, concept, required assets and continuous shot timings |
| Production directions | Camera action, on-screen copy, suggested audio, editing notes and CTA |
| Ready-to-use report | Responsive HTML, copyable scripts and a Markdown export |
| Research context | Source health, selection rules, exclusions and evidence limitations |

**A concrete example:** our manually reviewed LEGO sample becomes an 18-second original product script for a tote bag or everyday bag merchant. The brief carries the source link, observed hook and timed production directions together. [See the real sample →](docs/example-brief.md)

## Quick start

### 1. Get the project

```bash
git clone https://github.com/hey345437-boop/stillmore-tools.git
cd stillmore-tools
```

Requirements: **Python 3.10+**, network access and an AI host that can run local commands and inspect original video playback or frames. Collection and rendering use Python's standard library. Systems without an IANA timezone database may need `tzdata`.

### 2. Give it to your AI

Open the cloned folder in your AI coding assistant and paste:

```text
Read SKILL.md in this project and complete one full run.
Collect recent product videos, review the selected originals, and create
an HTML + Markdown brief with source links, creative breakdowns and
original remake scripts. Save the report locally and give me its path.
Use the configured thresholds. Mark videos you cannot inspect unavailable.
```

The agent instructions are [SKILL.md](SKILL.md). Your AI provides the creative analysis and video-viewing tools; the repository provides collection, structured output validation and rendering. No Stillmore account or paid feed API is required by the bundled collector. Your AI host's own usage costs still apply.

### 3. Make it a daily habit

After a successful manual run, use your AI host's scheduler to run **the full skill** at your chosen time and timezone. Keep this folder and its `state/` directory between runs. [Scheduling instructions and a copyable task prompt →](references/scheduling.md)

Downloading the repository does not activate a schedule. Running `scout.py` alone creates a research queue; it does not generate the finished AI breakdown.

## How selection works

The defaults in [sources.json](sources.json) are deliberately inspectable:

| Rule | Default |
| --- | --- |
| Discovery window | Last **7 days / 168 hours**, checked on each run |
| Original runtime | **1–59 seconds** |
| Public views | Strictly **above 10,000** |
| Ranking | Videos from the last 12 hours first; then views descending within each group |
| AI review queue | Up to **5 videos per run** |
| Report timezone | `Asia/Shanghai` |

Unknown publication times, runtimes or view counts fail selection. A day with no qualifying videos still gets a coverage report. Public views are a research signal, not proof of sales, organic reach or exceptional performance relative to an account's baseline.

Observations are stored locally in SQLite. Repeat observations can show view changes; an hourly rate is only calculated after an interval of at least one hour. Growth rate is **not** currently used for ranking. Feeds expose a limited recent history, so the seven-day window does not guarantee a complete seven-day archive.

## Source coverage

- **YouTube:** automatic discovery and public metric collection across 28 configured brand channels. Examples include LEGO, IKEA, Sephora, Rare Beauty, Scrub Daddy and Owala.
- **RSS and news:** 18 discovery feeds for campaigns, product demos, creator content and commerce trends.
- **TikTok / Instagram:** news-based discovery leads. Direct platform metric adapters are not included; a mention is not treated as a measured video.

Edit `sources.json` to change channels, feeds and thresholds. The starter list is a brand/campaign sample, not an exhaustive ecommerce ranking. Source availability and page formats may change.

The AI must inspect original footage before writing a breakdown. An inaccessible video is labelled unavailable. The validator checks structure, links, timestamps and script continuity; it cannot independently prove that an AI's interpretation is correct.

## Run the parts yourself

```bash
# Collect evidence, preserve observation history and prepare a review queue.
python3 scripts/scout.py

# Your AI reads the returned scan and analysis.request.json,
# reviews the original footage, and writes RUN/analysis.json.
# Replace RUN below with the run directory printed by the collector.
python3 scripts/render.py \
  --scan RUN/scan.json \
  --analysis RUN/analysis.json \
  --out RUN/report

# Check filtering boundaries and analysis/report validation.
python3 -m unittest discover -s tests -v
```

Outputs include `scan.json`, compressed feed evidence, `analysis.request.json`, and—after AI review—`report/index.html`, `report/report.md` and `report/validation.json`. See the [analysis contract](references/analysis-schema.md) for the required review fields.

The initial report interface uses Chinese labels. There is no implemented UI language switch; the AI can write the creative analysis in the requested language. The `report_language` config field is currently descriptive, not a renderer localization setting.

## Validation and scope

This is an early source release. A manual end-to-end local demo completed collection, original-video review and HTML/Markdown rendering. Nine automated tests cover selection boundaries, observation deltas and invalid analysis rejection. Unattended daily execution depends on the AI host and must be tested in that environment.

State, raw demo captures, credentials and personal configuration are excluded from this repository. The [published sample](docs/example-brief.md) is a dated excerpt, not a live feed. Remake scripts are original creative adaptations; source videos and brands remain their owners' material.

## From inspiration to production with Stillmore

**Trend Scout helps you decide what to make next. [Stillmore](https://stillmore.studio/) helps you create content from the business photos you already have.**

Keep researching with this standalone open-source workflow, or explore Stillmore for your product content workflow. No account or subscription is required to run Trend Scout. The website is a separate product; this repository does not contain its source code or an automatic video-generation integration.

## Contribute

Useful contributions include reliable source adapters, better evidence handling, report translations and documented test fixtures. Open an issue with a reproducible case. Do not include cookies, credentials or private customer data in reports or pull requests.

## License

[MIT](LICENSE) for the code and project documentation. Third-party videos, names and linked content are not relicensed by this project.
