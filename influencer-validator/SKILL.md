---
name: influencer-validator
description: Vet influencers / creators / KOLs and give a GO / CONDITIONAL / NO-GO verdict on using them in a campaign. Collects fresh posts, comments and engagers via Apify, the user's browser or uploaded exports (Instagram, TikTok, YouTube, LinkedIn, X) and checks median vs average engagement (≥5× = viral-skew no-go), views vs followers, bots and pods, who engages vs the ICP, relevant questions in comments, posting frequency vs engagement, best-performing content, brands and competitors in their content, and real use-case ability. Uses the project's product/ICP when in a project. Use whenever someone shares creator links or asks to vet, check, audit, shortlist or compare influencers, asks "is this creator legit / fake / worth it", "should we work with @handle", or plans influencer, UGC, ambassador or sponsored-post campaigns.
---

# Influencer validation

In crowded niches, follower counts and averages hide the truth. Some accounts look strong because of 1–2 viral posts, some buy bots or run engagement pods, and a big audience is worthless if the people engaging aren't the buyer. This skill checks what a *typical* post does, *who* engages, what content works for the creator, and whether their content already carries competing brands. Then it gives a verdict.

The yardstick comes from a study of 1,526 creator accounts and 23,120 posts. The creator you check may be in a different niche, so the skill judges mainly against **what good vs bad profiles look like** (`references/good-vs-bad-profiles.md`). Those patterns are ratios and transfer across niches. The AI/marketing percentiles (`references/benchmarks.md`) are used only when the creator is in that niche.

## Step 0: Connect Apify first, then fall back

The verdict is only worth something on **fresh** data, collected now. Never use old snapshots, cached numbers or remembered stats about a creator, and never present them as current. The study behind this skill supplies benchmarks only, no per-creator data.

Apify is the default data source. Check for it in this order, before any other work:

1. **Apify MCP connector already connected?** Look for its tools (`call-actor`, `fetch-actor-details`, `get-actor-output`; e.g. ToolSearch "apify call-actor"). If they are there, use the MCP route in step 2.
2. **`APIFY_TOKEN` set?** `[ -n "$APIFY_TOKEN" ] || grep -qs '^APIFY_TOKEN=' .env`. If yes, use the REST route in step 2.
3. **Neither: install the Apify MCP connector now**, and tell the user in one short message what you're doing and what they need to click. The user may be asked to approve in the interface; that is expected.
   - **Claude Code (terminal or desktop app, with a shell):** run
     `claude mcp add --transport http apify https://mcp.apify.com`
     (the user approves the command). Then tell them how to authorize: type `/mcp`, pick **apify**, choose **Authenticate**, log in to Apify in the browser window (a free account works) and click **Allow**. Its tools load after the connector reconnects; if they don't appear, restart the session (`claude --continue` keeps the conversation). If they already have an Apify API token, `claude mcp add --transport http apify https://mcp.apify.com --header "Authorization: Bearer <token>"` skips the browser step. They run that themselves; never ask them to paste the token into chat.
   - **Claude.ai, Claude desktop chat, Cowork or a cloud session:** if a connector tool is available (`SuggestConnectors`, `SearchMcpRegistry`), use it to show the Apify connector install card. Otherwise give the steps: **Settings → Connectors → Add custom connector**, name `Apify`, URL `https://mcp.apify.com`, **Add**, then **Connect**, log in to Apify and **Allow**. Connectors load when a chat or session starts, so they continue in a new one. In a cloud session, adding `APIFY_TOKEN` in the environment settings (environment menu → Edit → secrets or environment variables) also works.
   - Ask for the product and ICP in the same message if they are missing (step 1), then wait.
4. **Only if Apify isn't an option** (the user declines, can't sign up, or the connector won't authorize), offer the other fresh-data routes (details in `references/fresh-data-without-apify.md`):
   - **Collect it live in their browser** with the Claude in Chrome extension or the built-in browser, logged into the platform. LinkedIn, Instagram and X hide most data from logged-out visitors, so a server-side fetch is not enough.
   - **They upload the data:** the creator's own analytics export (best: audience job titles, seniority, industries and countries), a scraper export (PhantomBuster, Bright Data, Modash, HypeAuditor…) or screenshots, using the templates in `assets/`.

If no fresh data can be collected at all, stop and say what's needed. Don't produce a verdict.

**Reference first reply.** This is the most common start: links only, no Apify, no project. Keep to this shape and length, and adapt the platform details and the install steps to the surface you're in:

> To check these three on fresh data I use Apify, and it isn't connected yet. I won't judge them on old or remembered numbers.
>
> **Let's connect it (about 2 minutes, free account works):**
> 1. Approve the install prompt I'm about to run (`claude mcp add … apify`). In Claude.ai: Settings → Connectors → Add custom connector → `https://mcp.apify.com`.
> 2. Authorize it: type `/mcp` → **apify** → **Authenticate**, log in to Apify and click **Allow**.
>
> **Two things I need meanwhile:** the product or campaign, and your target buyer (role, seniority, company type, markets).
>
> If you'd rather not use Apify, I can read the profiles in your logged-in browser (Claude in Chrome), or you can upload the creators' analytics exports or screenshots.

## Step 1: Context and links (keep questions to a minimum)

The skill needs two things: **who the campaign is for** (product + ICP) and **the creator's social links**. Never ask for a price quote, rate, deliverables or budget. If the user mentions a price, use it.

**Inside a project** (project instructions or CLAUDE.md, product docs, positioning, ICP or brand-book files, a loaded brand skill, earlier discussion of the product), take the product, ICP, target markets and competitors from the project. Don't ask the user to restate them. Write them into `context.json` with `source` naming the files used, and print them as one line at the top of the report ("Validated against: …"). If the project has several products, pick the one the request relates to and say which.

**No project context:** ask once, in one short message, for (1) the product or campaign and (2) the ICP / target audience, plus the creator links if they're missing. Combine this with the step 0 notice when Apify is missing.

**Links:** if the user gave none, ask only for the links. Accept several links per creator (different platforms) and several creators.

**Competitors:** take them from the project. If they're missing, infer the obvious direct and near competitors from the product (a web search for "<product> alternatives" is fine). Don't ask.

`context.json` fields: `product`, `icp`, `markets`, `goal` (if known), `competitors`, `near_competitors`, `source`, optional `price_quote_usd`.

## Step 2: Collect fresh data (one folder per account; run accounts in parallel)

**With the Apify MCP connector:** the same actors and inputs as the REST script, run through `call-actor`:

```bash
python scripts/apify_fetch.py --url "<profile link>" --out runs/<handle>_<platform> --plan --only posts
```

Run each printed actor/input with `call-actor`. If it returns only a preview, fetch the full dataset with `get-actor-output`. Save the items as `runs/<handle>_<platform>/raw_mcp/<stage>.json`, then normalize them:

```bash
python scripts/apify_fetch.py --url "<profile link>" --out runs/<handle>_<platform> --raw-dir runs/<handle>_<platform>/raw_mcp --only posts
```

Repeat `--plan` / `--raw-dir` for `comments`, then `reactions` (LinkedIn) or `profiles` (Instagram, TikTok). The comment posts are picked from the saved posts, so each stage needs the one before it.

**With an `APIFY_TOKEN` (REST):**

```bash
python scripts/apify_fetch.py --url "<profile link>" --out runs/<handle>_<platform>
```

The platform is detected from the URL. Defaults: 25 recent posts, comments from 8 posts spread across low, middle and high performers (not just the viral one), up to 40 comments each, bios for up to 150 commenters (Instagram/TikTok), reactors with job headlines on LinkedIn. Report the Apify cost. If a stage fails or returns 0 items, see `references/apify-actors.md`. Don't continue silently with empty comments.

**Without Apify (browser or upload, only after step 0 ruled Apify out):** follow `references/fresh-data-without-apify.md`. Fill `assets/posts_template.csv` and `assets/engagers_template.csv` (from the browser, from exports, or by transcribing screenshots), then convert:

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
