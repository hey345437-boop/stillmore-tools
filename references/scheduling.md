# Deploy to an AI host

This package separates collection from creative analysis. A scheduled run must invoke the **host AI**, which reads the skill and uses its viewing tools; running only `scout.py` produces candidates, not a completed brief.

## Requirements

- Persistent local directory containing this entire folder.
- Python 3.10+, internet access, and an AI able to view video/frames.
- A host-provided scheduled-task feature and access to the folder on each run.
- User-selected local time, timezone and delivery destination.

## Scheduling prompt

Replace the folder path with the installation location when creating the host's task:

> Read SKILL.md in the Stillmore Trend Scout folder and complete one daily run. Collect current evidence, review each selected original video, and produce a report with original links, creative breakdowns and original remake scripts. Save the report locally and return its link in this chat. Keep the configured thresholds; report no qualifying videos honestly. Mark unviewable videos unavailable. Do not publish, send external messages, or change the source configuration. Retain previous observation state for the next run.

Set the recurrence using the host's supported scheduling UI/API, with the user's actual time and timezone. This document is not an active schedule. Installing this repository does not create a recurring task.

For Codex desktop, use its Automations feature. Other hosts need an equivalent scheduler and tool access; a text-only chat is insufficient. Desktop-hosted execution can depend on machine availability and the host's own scheduler behavior, which should be checked when deploying.

## A useful product promise

“Deploy to your AI. Receive a daily product-video research brief, with source links, creative breakdowns and remake scripts.”

Accompany it with: “Requires a compatible AI host with scheduled execution and video access. Source coverage and qualifying results vary; some days have no qualifying videos.”
