# Judgment rubric: what the model decides by reading

The scripts handle the arithmetic. These judgments need a reader. Write the results to `judgments.json` (schema in `scripts/verdict.py`). Keep counts honest: when unsure, label `unknown` — unknowns are excluded from the ICP share instead of inflating it.

## 1. Engager labels (who is interacting) → `engager_labels`

Read every entry in `to_classify.json → engagers` (bio / LinkedIn headline / sample comment). Compare it to the ICP the user gave you, not to "people interested in AI" in general — in this niche almost everyone is interested in AI.

| Label | Use when | Example for ICP "B2B SaaS marketing leads at 50–500 person companies" |
|---|---|---|
| `icp` | Bio/headline matches the role, industry or company type in the ICP | "Head of Growth @ Acme (Series B SaaS)" |
| `adjacent` | Could buy or influence, but not the core profile | "Freelance content marketer", "Founder, 2-person agency" |
| `non_icp` | Clear signal they are someone else | students, "AI art lover", crypto traders, job seekers when ICP is buyers, other creators farming engagement |
| `bot_or_spam` | Spam comment, "DM me", random-letter handle + no bio, crypto/forex promo, same comment text pasted on many posts | "Great post! Check my page 🔥" |
| `unknown` | Empty bio and a comment that says nothing about who they are | "🔥🔥" from `@j_k_4471` with no bio |

Method label: `"linkedin headlines"`, `"ig bios"`, `"tiktok bios"`, `"x bios"`, or `"comment content only"` (YouTube, or when bios failed). Comment-content-only labeling is weak evidence — confidence drops to medium at best.

Sample size: label all engagers if ≤ 300; otherwise label a random 300 and scale counts. Note geography if the ICP is regional (bios often state a country/city).

Put 3–5 short, representative examples into `examples` (role + one-line reason), including at least one negative one.

## 2. Comment labels (do people ask relevant questions?) → `comment_labels`

Start from the `heuristic` field, then correct it. Relevance is judged against the **product and ICP**.

| Label | Meaning |
|---|---|
| `relevant_question` | A real question about the use case, workflow, tool, pricing, setup, results — the kind a future buyer asks. "Does this work with HubSpot?", "How long did the setup take for your team?" |
| `substantive` | A real reaction with content: shares own experience, disagrees with a reason, adds a tip |
| `generic` | "Great post", "So true", "Love this", short praise, tags of friends |
| `cta_keyword` | One-word replies to a comment-to-get-link CTA ("GUIDE", "PROMPT"). Inflates engagement; says little about interest in *your* product |
| `spam_bot` | Spam, self-promo, scam, copy-paste |

Strong signal: relevant questions ≥ 10–15% of comments. In this niche many accounts sit below 3%. Also note whether the creator **answers** questions (`creator_reply_count` in metrics.json) — creators who reply drive more trust per post.

## 3. Content ↔ ICP match → `content_fit` (0–5)

Read the captions/transcripts in `posts_for_content_review`. Estimate the share of recent posts that are on topics the ICP cares about (`on_icp_topic_share_pct`).

- 5 — Most posts speak directly to the ICP's job and problems; the product would feel native.
- 4 — Clearly the right audience; some off-topic posts.
- 3 — Same broad space (AI / marketing) but a different angle or seniority (e.g. beginner "make money with AI" content for an enterprise tool).
- 2 — Overlap is accidental; product would feel like an ad break.
- 1 — Different audience (e.g. AI art, crypto, entertainment). → no-go.
- 0 — Off-topic or brand/agency account posing as a creator.

Also watch for: the account is really a brand or agency (research found many), heavy cross-posting of identical content across platforms (fine, but then the "audience" is the same people), recent sponsored posts for a direct competitor (add to `risks`).

## 4. Can they explain a product through a real use case? → `use_case` (0–5)

Find the creator's sponsored or tool-focused posts (look for #ad, "partner", "sponsored", tool names, demos). Judge the best one or two.

- 5 — Shows the tool solving a concrete problem end-to-end (real data/screen, before/after, numbers, steps the viewer can repeat). Audience questions follow.
- 4 — Real walkthrough of a workflow; some specifics missing.
- 3 — Feature tour or listicle ("10 AI tools you need"), accurate but not lived-in.
- 2 — Reads the brand's talking points; no demonstration.
- 1 — Hype only ("this AI will replace your team 🤯"), no explanation.
- 0 — No tool/product content to judge (score `null` instead of 0 if they simply never did one — then the verdict treats it as missing data and asks for a past example).

Cite the URL of the post you judged in `best_example_url`.

## 5. Niche and account type → `niche`, `niche_matches_reference`, `is_brand_account`

- `niche`: a few words, e.g. "AI tools for marketers", "home fitness", "personal finance for Gen Z".
- `niche_matches_reference`: `true` only if the creator is in AI / AI news / marketing with AI / SaaS / tech-for-business. Then the research percentiles (`benchmarks.md`) apply. Otherwise `false`: the scoring falls back to the niche-agnostic good/bad profile anchors (`good-vs-bad-profiles.md`). If the verdict is borderline and the niche differs, build a peer set (`scripts/peer_benchmark.py`).
- `is_brand_account`: `true` when the account is a company, agency, tool or school speaking as itself (no first-person voice, product-only feed, "we" bio). In the research, Instagram business accounts reached about a quarter of the peer engagement that personal accounts reached (0.38× vs 1.62×). This is a no-go for a creator campaign. A creator who *owns* a business but speaks in first person is not a brand account.

## 6. Audience geography and language → `geo_language` (0–5 or null)

Only score this when the ICP names markets or a language. Don't infer a country from a display name, emoji or flag in the handle; that is guesswork. Use evidence you can quote. Evidence: the language of comments, locations in engager bios/headlines, the creator's own language and location, time zones in the posting pattern.
- 5: clearly the target market and language. 3: mixed. 1: mostly another market. `null`: no signal, or the ICP has no market.

## 7. Content types → `post_tags` and `best_format_fit` (0–5)

Tag every sampled post with 1–2 content types, separated by `|`. Use the creator's own genres, for example: tutorial / walkthrough, tool review, listicle ("10 tools"), news / reaction, opinion / hot take, case study / results, behind the scenes, meme / entertainment, sponsored integration. The verdict script computes how each type performs against the creator's own median. Together with the format/length breakdown, this answers "what works best for this creator".

`best_format_fit`: can your product be shown naturally in the creator's best-performing type and format? 5 = the product fits their top type (e.g. a demo inside their 15-minute tutorials). 1 = you'd force them into a format that underperforms for them (e.g. a static post from a reels-first creator).

Then recommend the brief: format, length and angle, based on their best groups. For example: "Brief: long-form tutorial 10–15 min with the product solving one task end-to-end. Avoid Shorts (0.6× for this creator)."

## 8. Brands and competitors → `brands`

Start from `brand_mention_candidates` (@mentions, tagged accounts, linked domains, discount codes) and the captions of `sponsored_detected` posts. Add brands named in plain text (tool names, "thanks to X"). For each real brand:
- `relation`: `direct_competitor` (solves the same job for the same buyer), `near_competitor` (overlapping use case or an adjacent alternative the ICP compares against), `complementary` (integrates with or is used alongside the product), `unrelated`.
- `sponsored`: whether the post was a paid integration (disclosure, code, "partner", link with UTM).
- `last_date`.

Competitor list: use `competitors` / `near_competitors` from context.json first. If they are missing, infer the obvious alternatives from the product description. You may use web search for "<product> alternatives". Don't ask the user.

`competitor_conflict`:
- `direct_recent`: paid post for a direct competitor in the last ~60 days. → CONDITIONAL: check exclusivity. The audience has just heard a rival pitch.
- `direct_old`: a direct competitor, older than that or unpaid mentions only.
- `near`: near competitors only.
- `none`.

Don't read competitor presence only as a negative. A creator who reviews the category means the audience is in-market; say so in the evidence. Heavy ad load (> 30% of posts are deals) lowers trust per post, whatever the brands are.
