---
name: influencer-validator
description: Vet influencers / creators / KOLs and give a GO / CONDITIONAL / NO-GO verdict on using them in a campaign. Collects fresh posts, comments and engagers via Apify, the user's browser or uploaded exports (Instagram, TikTok, YouTube, LinkedIn, X) and checks median vs average engagement (≥5× = viral-skew no-go), views vs followers, bots and pods, who engages vs the ICP, relevant questions in comments, posting frequency vs engagement, best-performing content, brands and competitors in their content, and real use-case ability. Uses the project's product/ICP when in a project. Use whenever someone shares creator links or asks to vet, check, audit, shortlist or compare influencers, asks "is this creator legit / fake / worth it", "should we work with @handle", or plans influencer, UGC, ambassador or sponsored-post campaigns.
---

# Influencer validation

In crowded niches, follower counts and averages hide the truth. Some accounts look strong because of 1–2 viral posts, some buy bots or run engagement pods, and a big audience is worthless if the people engaging aren't the buyer. This skill checks what a *typical* post does, *who* engages, what content works for the creator, and whether their content already carries competing brands. Then it gives a verdict.

The yardstick comes from a study of 1,526 creator accounts and 23,120 posts. The creator you check may be in a different niche, so the skill judges mainly against **what good vs bad profiles look like** (`references/good-vs-bad-profiles.md`). Those patterns are ratios and transfer across niches. The AI/marketing percentiles (`references/benchmarks.md`) are used only when the creator is in that niche.

## Step 0: Check data access first and say so immediately

The verdict is only worth something on **fresh** data, collected now. Never use old snapshots, cached numbers or remembered stats about a creator, and never present them as current. (The study behind this skill supplies benchmarks only, no per-creator data.)

Before anything else, check whether Apify is available: `APIFY_TOKEN` in the environment or in `.env`, or an Apify MCP connector (tools like `call-actor`).

```bash
[ -n "$APIFY_TOKEN" ] || grep -qs '^APIFY_TOKEN=' .env && echo apify-ok || echo no-apify
```

**If there's no Apify access, say it in your very first message** before doing any work, and offer the fresh-data routes (details in `references/fresh-data-without-apify.md`):

1. **Add an Apify token** (fastest, full check, ~$0.30–1.50 per account). They create one at console.apify.com → Settings → Integrations and store it as `APIFY_TOKEN`: in a cloud session via the environment settings (environment menu → Edit → secrets / environment variables; a new session picks it up), locally in `.env`. Never ask them to paste the token into chat.
2. **Collect it live in their browser.** Use the Claude in Chrome extension or the built-in browser, logged into the platform. LinkedIn, Instagram and TikTok hide most data from logged-out visitors, so a server-side fetch is not enough. In a cloud session this needs their computer connected, or a Claude desktop/Chrome session.
3. **They upload the data:** native analytics exports, a scraper export (PhantomBuster, Bright Data, Modash, HypeAuditor…) or screenshots, using the templates in `assets/`. The best source is the creator's own analytics (LinkedIn creator analytics, TikTok/IG insights, YouTube Studio): these show audience job titles, seniority, industries and countries, the strongest ICP evidence there is.

Put this in the same single message as any missing context questions (step 1), then wait for their choice. If they name a route, follow it; don't re-ask.

**Reference first reply.** This is the most common start: links only, no Apify, no project. Keep to this shape and length, and adapt the platform details:

> I can't pull fresh data on these three yet. This session has no Apify access, and I won't judge them on old or remembered numbers. LinkedIn also hides posts and reactor lists from logged-out visitors, so I can't fetch them from here directly.
>
> **Pick one way to get fresh data:**
> 1. **Add an Apify token.** Fastest; runs the full check for about $0.30–1.50 per creator. Create it at console.apify.com → Settings → Integrations, then add it as `APIFY_TOKEN` in this environment's settings (environment menu → Edit → secrets or environment variables). A new session picks it up. Please don't paste the token into chat.
> 2. **Collect it in your browser.** I read each profile's recent posts, reactions, comments and the job headlines of the people engaging while you're logged in. This needs Claude desktop with the Chrome extension, or your computer connected to this session.
> 3. **Upload the data.** Best is each creator's own analytics export (Content and Audience tabs: job titles, seniority, industries, countries). Scraper exports or screenshots also work, and I'll give you a CSV template.
>
> **Two things I need either way:** the product or campaign, and your target buyer (role, seniority, company type, markets).
>
> I'll work out the likely competitors myself. Once I have the data, each creator gets GO / CONDITIONAL / NO-GO, plus a ranked comparison.

## Step 1: Context and links (keep questions to a minimum)

The skill needs two things: **who the campaign is for** (product + ICP) and **the creator's social links**. Never ask for a price quote, rate, deliverables or budget. If the user mentions a price, use it.

**Inside a project** (project instructions or CLAUDE.md, product docs, positioning, ICP or brand-book files, a loaded brand skill, earlier discussion of the product), take the product, ICP, target markets and competitors from the project. Don't ask the user to restate them. Write them into `context.json` with `source` naming the files used, and print them as one line at the top of the report ("Validated against: …"). If the project has several products, pick the one the request relates to and say which.

**No project context:** ask once, in one short message, for (1) the product or campaign and (2) the ICP / target audience, plus the creator links if they're missing. Combine this with the step 0 notice when Apify is missing.

**Links:** if the user gave none, ask only for the links. Accept several links per creator (different platforms) and several creators.

**Competitors:** take them from the project. If they're missing, infer the obvious direct and near competitors from the product (a web search for "<product> alternatives" is fine). Don't ask.

`context.json` fields: `product`, `icp`, `markets`, `goal` (if known), `competitors`, `near_competitors`, `source`, optional `price_quote_usd`.

## Step 2: Collect fresh data (one folder per account; run accounts in parallel)

**With Apify:**

```bash
python scripts/apify_fetch.py --url "<profile link>" --out runs/<handle>_<platform>
```

The platform is detected from the URL. Defaults: 25 recent posts, comments from 8 posts spread across low, middle and high performers (not just the viral one), up to 40 comments each, bios for up to 150 commenters (Instagram/TikTok), reactors with job headlines on LinkedIn. Report the Apify cost. If a stage fails or returns 0 items, see `references/apify-actors.md`. Don't continue silently with empty comments.

**Without Apify (browser or upload):** follow `references/fresh-data-without-apify.md`. Fill `assets/posts_template.csv` and `assets/engagers_template.csv` (from the browser, from exports, or by transcribing screenshots), then convert:

```bash
python scripts/import_manual.py --platform linkedin --handle <handle> --followers <n> --source "browser 2026-11-05" \
  --posts posts.csv [--engagers engagers.csv] [--audience audience.csv] --out runs/<handle>_<platform>
```

From here on everything is identical: the same metrics, judgment pass and verdict. Record only what the page or file actually shows. If a number isn't visible, leave it empty; never estimate it. Smaller manual samples (10–15 posts, 3–5 posts' worth of engagers) are fine, and the report states the sample size.

If no fresh data can be collected (no token, no browser, nothing uploaded), stop and say what's needed. Don't produce a verdict.

## Step 3: Hard metrics

```bash
python scripts/compute_metrics.py --dir runs/<handle>_<platform>
```

Uses settled posts only (≥48h old, not pinned, last 90 days). Writes `metrics.json` + `to_classify.json` and prints flags:

- **NO-GO:** average ≥ 5× median engagement · best post ≥ 50% of all engagement · 21+ posts/week with ER < 0.1% · ≥30% of profile-checked engagers look like bots.
- **WARN:** skew 3–5× · median views < 0.05× followers (dead/bought followers) · posting above the platform's danger level · per-post engagement falls in busier weeks · declining trend · emoji/spam or duplicate comments · keyword-CTA comment bait · engagement pod · > 30% of posts are ads · sponsored posts underperform · business account · inactive · small sample.

It also computes posting frequency vs engagement (sweet-spot band, busy-week correlation, posts < 6h apart), a content breakdown (format, length, caption length, hashtags, sponsored vs organic, each vs the creator's own median), the 30-day trend, and brand-mention candidates.

## Step 4: Judgment pass

Read `to_classify.json` and follow `references/judgment-rubric.md`. Write `judgments.json`:

1. **Who engages:** label each engager `icp` / `adjacent` / `non_icp` / `bot_or_spam` / `unknown` against *this* ICP. In crowded niches almost everyone is "interested in the topic"; the bar is whether this person would buy or influence buying *this* product. Prefer `unknown` to a hopeful `icp`.
2. **Comments:** relevant buyer-type questions vs substantive vs generic, keyword-CTA replies and spam.
3. **Content fit** (0–5) and **geography/language** match (0–5, or null when there's no market).
4. **Content types:** tag every post (tutorial, review, listicle, news, opinion, case study, …) so the script can show which types work for this creator. Then score whether the product fits their best format.
5. **Brands and competitors:** which brands appear, whether paid, how each relates to the product (direct / near competitor, complementary, unrelated), and the latest date. Set `competitor_conflict`.
6. **Use case** (0–5): judge past tool/sponsored posts. Real problem solved end-to-end, or talking points? Cite the URL. Use `null` if they have never done one.
7. **Niche and account type:** does the AI/marketing research apply (`niche_matches_reference`)? Is this a brand/agency account rather than a person?

Quote short real examples (an engager headline, a comment). They make the verdict believable to whoever signs off the budget.

If the creator is in a different niche *and* the verdict is close (score 45–75), calibrate. Fetch 5–8 similar-size peers in that niche with `--only posts`, run `scripts/peer_benchmark.py`, and re-run metrics with `--peers`.

## Step 5: Verdict

```bash
python scripts/verdict.py --dir runs/<handle>_<platform> --context runs/context.json
```

Score out of 100, in four groups:

| Group | Criteria (points) |
|---|---|
| A. Real reach & consistency (35) | median vs average, no viral skew (10) · median views ÷ followers (10) · median ER vs niche or good/bad anchors (10) · posting frequency & trend (5) |
| B. Audience fit (35) | ICP share of engagers (20) · content ↔ ICP (10) · geography/language (5) |
| C. Audience quality (15) | relevant questions in comments (10) · engagement depth: comments/shares/saves, creator replies (5) |
| D. Brand fit (15) | real use-case ability (8) · brands & competitors situation (4) · product fits their best format (3) |

LinkedIn has no views, so those points move to consistency. Unchecked criteria are excluded rather than scored zero, and confidence drops.

- **NO-GO:** any NO-GO flag; ICP share of engagers < 15%; labeled bots ≥ 30%; content fit ≤ 1; brand/agency account; or score < 50.
- **CONDITIONAL:** score 50–69; or ≥ 70 with 3+ warnings; or a recent paid post for a direct competitor (check exclusivity); or a geography/language mismatch. State the condition: test post first, pay per result, ask for audience-demographics screenshots, brief a specific format.
- **GO:** score ≥ 70, no gates, ≤ 2 warnings, no conditions.

## Step 6: Report

`verdict.py` writes `report.md`. Replace the `<!-- SUMMARY -->` line with 3–5 plain sentences: the verdict, the one or two numbers that decided it, and the next action. Add a short **Brief recommendation** based on the creator's best-performing format and content type. Save it in the user's working folder, show the summary in chat, and give the file path.

For several accounts, also run:

```bash
python scripts/compare.py --dirs runs/* --person "Name=runs/a_tiktok,runs/a_instagram" --out runs/comparison.md
```

This produces a ranked table. For a person with several platforms, it shows which account to buy and whether they cross-post the same content (overlapping audiences, so buying both adds less reach than the follower counts suggest).

## Principles

- **Median over average.** The average describes the best post; the median describes what you're buying. Show both.
- **Reach to own followers exposes fake audiences.** Good and bad accounts get the same engagement per view; bad ones simply reach a sixth or less of their followers.
- **ICP engagement is the real ER.** ICP-weighted ER = median ER × ICP share. A 4% ER at 5% ICP loses to 1% at 40%.
- **More posts ≠ more value.** Every platform has a frequency sweet spot. Above it, each post (including yours) gets less.
- **Buy the format that works for them.** Brief the creator's best content type, not the brand's favourite format.
- **Missing data is not a pass.** Say what wasn't checked and what would settle it. Never invent numbers or engagers, and never put the Apify token in outputs.
