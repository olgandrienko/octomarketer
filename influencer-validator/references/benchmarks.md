# AI / marketing niche percentiles

Use these only when the creator is in AI / marketing / SaaS / tech-for-business (`niche_matches_reference: true`). For any other niche, use `good-vs-bad-profiles.md`. It holds the niche-agnostic patterns and is the main yardstick.

Source: 1,526 core AI/marketing creator accounts (2k–150k followers), scraped with Apify on 2026-10-08 (Instagram, TikTok) and 2026-10-20 (YouTube, LinkedIn, X). Machine-readable copy: `data/benchmarks.json` (the scripts use that file).

Engagement definitions (keep these when you compare a creator to the table):

- Instagram = likes + comments. TikTok = likes + comments + shares + saves. YouTube = likes + comments.
- LinkedIn = reactions + comments + reposts (no views on LinkedIn). X = likes + replies + reposts + quotes + bookmarks (X views are impressions).
- Median ER = median engagement per post / followers × 100. This is the number the skill scores on — not the average.

## Key facts from the research

- **169 core accounts (11%) had average engagement ≥ 5× their median.** By platform: TikTok 65 of 243, X 34, YouTube 31, Instagram 30, LinkedIn 9. These accounts look strong on averages because of 1–2 viral posts. The skill treats this as a no-go.
- 79 accounts were "one-hit" (best post = 50%+ of sample engagement). 48 looked like automated/bulk posting (21+ posts/week with ER < 0.1%). 163 posted less than every two weeks.
- Smaller accounts engage better almost everywhere: on X, median ER is 2.0% at 2k–10k but 0.26% at 50k–150k; on TikTok, 3.2% vs 1.25%. Price per follower should fall as size rises, not rise.
- Cross-posting is common (78 of 135 multi-platform creators clearly post the same content everywhere). The same post usually performs best on TikTok vs Instagram, on X vs LinkedIn, and on TikTok vs YouTube. Validate the platform you are actually buying.

## Instagram

| Tier | Median ER % p25 / p50 / p75 | Median views÷followers p25 / p50 / p75 | ER by views % p50 / p90 | Avg÷median engagement p50 / p90 | Posts/week p50 |
|---|---|---|---|---|---|
| all | 0.0373 / 0.207 / 0.77 | 0.0246 / 0.0934 / 0.302 | 2.69 / 5.96 | 1.58 / 7.47 | 2.78 |
| 2k-10k | 0.0379 / 0.284 / 0.904 | 0.0306 / 0.122 / 0.457 | 2.56 / 5.53 | 1.47 / 6.46 | 2.27 |
| 10k-50k | 0.0285 / 0.126 / 0.429 | 0.0214 / 0.0805 / 0.206 | 2.9 / 6.41 | 1.77 / 11.2 | 3.31 |
| 50k-150k | 0.0279 / 0.137 / 0.684 | 0.0259 / 0.0788 / 0.225 | 2.94 / 6.92 | 1.9 / 7.03 | 3.62 |

## TikTok

| Tier | Median ER % p25 / p50 / p75 | Median views÷followers p25 / p50 / p75 | ER by views % p50 / p90 | Avg÷median engagement p50 / p90 | Posts/week p50 |
|---|---|---|---|---|---|
| all | 0.196 / 0.536 / 1.51 | 0.038 / 0.098 / 0.247 | 7.71 / 11.8 | 2.85 / 13.3 | 4.93 |
| 2k-10k | 0.467 / 0.85 / 1.91 | 0.0949 / 0.192 / 0.371 | 6.43 / 11.5 | 2.58 / 13.5 | 4.83 |
| 10k-50k | 0.258 / 0.468 / 1.13 | 0.0363 / 0.0711 / 0.166 | 7.99 / 11.9 | 2.93 / 17.6 | 5.31 |
| 50k-150k | 0.094 / 0.245 / 0.974 | 0.017 / 0.0367 / 0.131 | 8.47 / 11.9 | 3.53 / 10.9 | 4.93 |

## YouTube

| Tier | Median ER % p25 / p50 / p75 | Median views÷followers p25 / p50 / p75 | ER by views % p50 / p90 | Avg÷median engagement p50 / p90 | Posts/week p50 |
|---|---|---|---|---|---|
| all | 0.0312 / 0.115 / 0.42 | 0.0249 / 0.0814 / 0.248 | 1.72 / 3.57 | 1.81 / 6.09 | 0.97 |
| 2k-10k | 0.0407 / 0.157 / 0.721 | 0.0292 / 0.118 / 0.345 | 2.05 / 3.65 | 1.8 / 7.08 | 0.9 |
| 10k-50k | 0.021 / 0.0909 / 0.349 | 0.0233 / 0.067 / 0.176 | 1.49 / 3.8 | 1.82 / 6.73 | 0.94 |
| 50k-150k | 0.0299 / 0.107 / 0.289 | 0.0269 / 0.0739 / 0.192 | 1.54 / 3.42 | 1.84 / 3.9 | 1.16 |

## LinkedIn

| Tier | Median ER % p25 / p50 / p75 | Median views÷followers p25 / p50 / p75 | ER by views % p50 / p90 | Avg÷median engagement p50 / p90 | Posts/week p50 |
|---|---|---|---|---|---|
| all | 0.0398 / 0.123 / 0.367 | n/a | n/a | 1.49 / 2.82 | 3.51 |
| 2k-10k | 0.0415 / 0.134 / 0.428 | n/a | n/a | 1.5 / 2.85 | 2.75 |
| 10k-50k | 0.0336 / 0.105 / 0.315 | n/a | n/a | 1.48 / 2.7 | 4.19 |
| 50k-150k | 0.0825 / 0.228 / 0.447 | n/a | n/a | 1.43 / 3.8 | 7.31 |

## X

| Tier | Median ER % p25 / p50 / p75 | Median views÷followers p25 / p50 / p75 | ER by views % p50 / p90 | Avg÷median engagement p50 / p90 | Posts/week p50 |
|---|---|---|---|---|---|
| all | 0.226 / 0.581 / 1.45 | 0.0801 / 0.174 / 0.415 | 2.63 / 8.59 | 1.42 / 3.88 | 14.1 |
| 2k-10k | 0.595 / 1.45 / 2.8 | 0.129 / 0.251 / 0.526 | 3.97 / 11.4 | 1.37 / 3.85 | 14.1 |
| 10k-50k | 0.258 / 0.492 / 0.94 | 0.0719 / 0.169 / 0.379 | 2.28 / 6.63 | 1.34 / 3.47 | 13.3 |
| 50k-150k | 0.0836 / 0.145 / 0.227 | 0.0354 / 0.0944 / 0.204 | 1.94 / 3.75 | 1.67 / 4.82 | 19.6 |

How to read a percentile: p50 = a typical creator in this niche and size. The scorecard gives full points at p75+ and zero at p10 or below. Creators outside 2k–150k are compared to the nearest tier; say so in the report.
