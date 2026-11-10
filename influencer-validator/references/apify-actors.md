# Apify actors used by `scripts/apify_fetch.py`

These are the same actor families the research study used (posts, comments, profiles). Read this file when a fetch fails, returns 0 items, or the user asks what it costs.

| Platform | Posts + profile | Comments | Who the engagers are |
|---|---|---|---|
| Instagram | `apify/instagram-scraper` (resultsType=posts) + `apify/instagram-profile-scraper` | `apify/instagram-comment-scraper` | commenter bios via `apify/instagram-profile-scraper` |
| TikTok | `clockworks/tiktok-scraper` (profiles) | `clockworks/tiktok-comments-scraper` | commenter bios via `clockworks/tiktok-profile-scraper` |
| YouTube | `streamers/youtube-scraper` (channel URL) | `streamers/youtube-comments-scraper` | no bios exposed → classify from comment content (lower confidence) |
| LinkedIn | `harvestapi/linkedin-profile-posts` + `harvestapi/linkedin-profile-scraper` | `harvestapi/linkedin-post-comments` | `harvestapi/linkedin-post-reactions` — reactors come with **headlines (job title + company)**, the best ICP signal of any platform |
| X | `apidojo/tweet-scraper` (`from:handle -filter:replies -filter:retweets`) | same actor, `conversation_id:<id>` | reply authors come with bio + follower count inline |

## Typical cost per creator (defaults: 25 posts, 8 posts × 40 comments, ≤150 bios)

Roughly USD 0.30–1.50 per creator. The research run cost USD 85.61 for ~1,000 accounts across YouTube/LinkedIn/X. `fetch_log.json` records `usd` per actor run; report the total to the user. Lower `--comments-per-post` / `--max-profiles` for big batches.

## Access: MCP connector first, token second

- **Apify MCP connector** (preferred): `https://mcp.apify.com`, authorized with OAuth (an Apify login in the browser). Claude Code: `claude mcp add --transport http apify https://mcp.apify.com`, then `/mcp` → apify → Authenticate. Claude.ai / desktop / Cowork: Settings → Connectors → Add custom connector. Tools used: `call-actor` (run an actor with an input), `get-actor-output` (full dataset items when `call-actor` returns a preview), `fetch-actor-details` (current input schema). Run the actors with the inputs that `apify_fetch.py --plan` prints, save the items to `raw_mcp/<stage>.json`, and normalize them with `--raw-dir`.
- **`APIFY_TOKEN`** (REST, `apify_fetch.py` without flags): in the environment or in `.env`. Create one at console.apify.com → Settings → Integrations. In a cloud session it goes in the environment settings (secrets or environment variables), which a new session picks up. Never ask the user to paste it into chat, never print it, and never write it into report files.

## When a stage fails or returns 0 items

1. Re-run that stage only: `--url <link> --out <same dir> --only comments` (stages: posts, comments, reactions, profiles). Earlier stage files are reused.
2. Add `--show-input` to see the exact input sent.
3. Compare it with the actor's current input schema (Apify console, or `fetch-actor-details` over MCP). Actor authors rename fields from time to time.
4. Pass corrections with `--input-override '{"comments": {"maxComments": 50}}'` (keys are stage names: posts, profile, comments, reactions, profiles).
5. If an actor is gone, pick a replacement with the same output and update the `ACTORS` table at the top of the script.

Known quirks (from the research):
- YouTube: hidden likes show as 0 — check for many posts with views but 0 likes; exclude them from the engagement median and say so. Channel scrapes can be slow; the script aborts at 15 minutes.
- LinkedIn: no views. Profile follower count = profile followers (not connections). The post scraper can stop at its cost limit and return few posts.
- X: search returns roughly 50–75 tweets per query; very active accounts may only cover a few days. Use `--posts 60` for heavy posters.
- Instagram: some posts have likes hidden (`likesCount` = -1 or null) — exclude them.
- TikTok: pinned videos are often old viral hits; the script excludes `isPinned`.

## No Apify access at all

Tell the user straight away, then use `fresh-data-without-apify.md`: their logged-in browser (Claude in Chrome / built-in browser), another scraper's export, or uploaded analytics and screenshots. Never fall back to old or remembered numbers about a creator. If no fresh data can be collected, there is no verdict.
