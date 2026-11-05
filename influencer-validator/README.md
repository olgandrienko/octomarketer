# influencer-validator

Checks an influencer / creator before a campaign and returns **GO / CONDITIONAL / NO-GO**.

- Collects **fresh** posts, comments and engagers with Apify, or without Apify via the user's logged-in browser (Claude in Chrome) or uploaded analytics/scraper exports (Instagram, TikTok, YouTube, LinkedIn, X). Never uses old snapshots.
- Median vs average engagement (average ≥ 5× median = no-go), views vs followers, bots, engagement pods
- Share of engagers who match the ICP, relevant questions in comments, real use-case ability
- Posting frequency vs engagement, which content performs best, brands and competitors in their content
- Compares against good vs bad profile patterns from a study of 1,526 AI/marketing creator accounts and 23,120 posts (Oct 2026)

## Install

- **Claude.ai / Cowork:** download `influencer-validator.skill` from this repo and upload it under Settings → Capabilities → Skills.
- **Claude Code:** copy this folder to `~/.claude/skills/influencer-validator/` (or `.claude/skills/` in a project).

Best with an `APIFY_TOKEN` in the environment or a `.env` file. Without one, the skill says so straight away and offers the browser or upload routes (templates in `assets/`).

## Layout

- `SKILL.md`: workflow and verdict rules
- `scripts/`: `apify_fetch.py` or `import_manual.py` → `compute_metrics.py` → `verdict.py`, plus `compare.py` and `peer_benchmark.py`
- `assets/`: CSV templates for browser-collected or uploaded data
- `references/`: good vs bad profiles, AI-niche benchmarks, judgment rubric, Apify notes, fresh data without Apify
- `data/`: benchmarks from the study (no per-creator data)
