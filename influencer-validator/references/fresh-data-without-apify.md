# Fresh data without Apify

Use this when there's no Apify token. The rule doesn't change: **only data collected now, from the live account or from the creator's own current analytics.** No old snapshots and no remembered numbers. Every number in the report must trace back to something the browser showed or a file the user gave you today.

## Which route works where

| Platform | Logged-out fetch (WebFetch / headless browser) | Logged-in browser (Claude in Chrome, built-in browser) | Best upload |
|---|---|---|---|
| LinkedIn | ❌ authwall (HTTP 999) | ✅ posts, reactions, comments, **reactor and commenter headlines** | Creator analytics export (posts + audience demographics: job titles, seniority, industry, company size, location) |
| Instagram | ❌ mostly blocked | ✅ posts, likes, reel plays, comments; bios one profile at a time | Insights screenshots: reach per post, audience countries, ages |
| TikTok | ⚠️ partly (view counts on the profile grid sometimes load) | ✅ views per video on grid, likes, comments, shares, saves | TikTok Studio: per-video analytics, audience countries |
| YouTube | ✅ public: views, likes (if shown), comments, upload dates | ✅ same | YouTube Studio export: views, watch time, audience geography |
| X | ❌ login needed for timelines | ✅ views, likes, reposts, replies, bookmarks; reply authors with bios | Analytics export (impressions, engagements per post) |

Try a quick logged-out fetch only for YouTube (and maybe TikTok). For the others, go straight to the browser or an upload. Don't burn time on authwalls.

## Route A: collect in the user's browser

Tools: Claude in Chrome (`mcp__claude-in-chrome__*`), the built-in browser (`mcp__Claude_Browser__*`), or the same tools through a connected computer (`mcp__remote-devices__*`). If none is available in this session, say so and offer the other routes. In a cloud session, the user can connect their computer, or run the check from Claude desktop with the Chrome extension.

Work in a new tab. Read pages as text. Don't click like, follow, connect or comment, and don't message anyone. Collect for **at least 12 recent posts** (25 if quick) and engagers from **4–6 posts** spread across strong, typical and weak ones.

**LinkedIn**
1. Profile page → follower count (shown as "X followers" under the headline or in the activity section). Copy the headline and about text: that's the creator bio.
2. `https://www.linkedin.com/in/<handle>/recent-activity/all/` → for each original post (skip reposts unless they added commentary): post URL ("Copy link to post"), relative date → convert to an absolute date, format (text / image / multi-image / document / video / poll / article / quote post), reactions count, comments count, reposts count, first ~300 characters of text.
3. For 4–6 posts: open the reactions list → name + headline for up to ~50 people. Open the comments → name + headline + comment text. Mark the creator's own replies.
4. Note any brand tags (@Company), "sponsored", "partner" or "#ad" markers, and links.

**Instagram:** profile → followers, bio. Posts grid / Reels tab → for each post: URL, date (open the post), type, likes, comments, plays for reels. Comments → username + text; open 30–50 commenter profiles for bios.

**TikTok:** profile → followers, bio. Grid shows views per video. Open each video for likes, comments, shares, saves, date. Comments → username + text.

**YouTube:** `/videos` and `/shorts` tabs → titles, views, dates; open videos for likes and comment count; comments → author + text (no bios on YouTube).

**X:** profile → followers, bio. Posts tab → views, likes, reposts, replies, bookmarks, date, URL. Open replies → author, bio (hover card or profile), text.

Write what you collect into the CSV templates as you go (one row per post, one row per engager action), then run `import_manual.py`.

## Route B: user uploads data

Ask for what's easiest for them. Accept anything, and convert it into the templates:
- **Best:** the creator's native analytics, which agencies can request from the creator. LinkedIn creator analytics export (Content + Audience tabs), TikTok Studio, Instagram Insights, YouTube Studio. These give impressions/reach per post and audience demographics. On LinkedIn, the audience tab's job titles, seniority, industries and company size are direct ICP evidence. Put them in `assets/audience_template.csv`.
- **Scraper exports:** PhantomBuster, Bright Data, Modash, HypeAuditor, Upfluence, Favikon, or the user's own spreadsheet. Map the columns to the templates. `import_manual.py` already understands common column names (reactions → likes, impressions → views, and so on).
- **Screenshots:** read them and transcribe numbers exactly. Never fill gaps by estimating. Say in the report that the data was transcribed from screenshots.

Templates (copy and fill; header names matter, extra columns are ignored):
- `assets/posts_template.csv`: `url, date, format, views, likes, comments, shares, saves, caption, duration_s, sponsored, pinned`
- `assets/engagers_template.csv`: `post_url, name, headline_or_bio, action (comment|reaction), comment_text, is_creator_reply`
- `assets/audience_template.csv`: `dimension (job_title|seniority|industry|company_size|location|age|gender), value, share_pct`

## Audience demographics change the ICP check

If an audience file is provided, `import_manual.py` saves it as `audience.json`. Use it in the judgment pass: the ICP share is better measured on the creator's whole audience (e.g. "Marketing 22%, Senior 31%, Software industry 18%") than on a sample of 100 engagers. When both exist, report both and let the higher-quality source drive `engager_labels`.
