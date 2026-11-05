#!/usr/bin/env python3
"""
Compute the hard numbers for one creator account from the normalized files that
apify_fetch.py writes (or files you build by hand in the same shape).

Usage:
  python compute_metrics.py --dir ./runs/someuser_tiktok [--window-days 90] [--min-age-hours 48]
                            [--peers ./runs/peers.json]   # optional niche peer reference (peer_benchmark.py)

Reads:  profile.json, posts.json, comments.json (optional), engagers.json (optional)
Writes: metrics.json      - numbers, good/bad-profile position, flags, content breakdown, brand candidates
        to_classify.json  - posts, engagers and comments for the model's judgment pass

Two references are reported side by side:
  * profile  - niche-agnostic: where the account sits between the median BAD and median GOOD profile
               of its platform (ratios: consistency, views/followers, comment share, frequency band)
  * niche    - AI/marketing percentiles from the research (only meaningful if the creator is in that
               niche) or a peer file built for the creator's own niche
"""
import argparse, json, math, os, re, statistics as st
from collections import Counter, defaultdict
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = json.load(open(os.path.join(HERE, "..", "data", "benchmarks.json")))
PLAT_NAME = {"instagram": "Instagram", "tiktok": "TikTok", "youtube": "YouTube", "linkedin": "LinkedIn", "x": "X"}

# Engagement definitions match the research study so numbers are comparable.
ENG_FIELDS = {
    "instagram": ["likes", "comments"],
    "tiktok": ["likes", "comments", "shares", "saves"],
    "youtube": ["likes", "comments"],
    "linkedin": ["likes", "comments", "shares"],
    "x": ["likes", "comments", "shares", "quotes", "saves"],
}

EMOJI_RE = re.compile(r"^[\W_\s\d]*$", re.UNICODE)
GENERIC = {"nice", "great", "wow", "amazing", "cool", "awesome", "love it", "love this", "great post", "nice post",
           "thanks", "thank you", "so true", "facts", "agreed", "great share", "well said", "insightful",
           "very informative", "great content", "keep it up", "fire", "this", "yes", "100%", "true", "interesting",
           "great insights", "thanks for sharing", "great info", "good", "super", "perfect", "helpful", "informative"}
SPAM_RE = re.compile(r"(dm me|check my (profile|bio|page)|promote|collab\?|send (pic|it) to|follow me|"
                     r"crypto|forex|investment|earn \$|whatsapp|telegram|t\.me/|bit\.ly)", re.I)
QUESTION_RE = re.compile(r"\?|^(how|what|which|does|do|can|is|are|where|why|when|will|would|could|should)\b", re.I)
CTA_KEYWORD_RE = re.compile(r"^[A-Z0-9]{2,15}[!.]*$")
SPONSOR_RE = re.compile(r"(#ad\b|#ads\b|#sponsored|#partner\b|#paidpartnership|#werbung|#anzeige|paid partnership|"
                        r"sponsored by|in partnership with|partnered with|thanks to \S+(?: \S+){0,3} for sponsoring|"
                        r"this (video|post) is sponsored|today'?s sponsor|brought to you by|use (my )?code|promo code|"
                        r"discount code|affiliate link|#collab\b|#gifted)", re.I)
MENTION_RE = re.compile(r"(?<![\w.])@([A-Za-z0-9_][A-Za-z0-9_.]{1,29})")
CODE_RE = re.compile(r"\b(?:code|coupon)\s*[:\-]?\s*([A-Z0-9]{3,15})\b")
DOMAIN_RE = re.compile(r"https?://(?:www\.)?([a-z0-9\-]+\.[a-z.]{2,10})", re.I)
LINK_HOSTS_IGNORE = {"youtube.com", "youtu.be", "instagram.com", "tiktok.com", "x.com", "twitter.com", "t.co",
                     "linkedin.com", "lnkd.in", "linktr.ee", "beacons.ai", "stan.store", "bit.ly", "facebook.com"}


def parse_dt(s):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def eng_of(p, plat):
    vals = [p.get(f) for f in ENG_FIELDS[plat]]
    if all(v is None for v in vals):
        return None
    vals = [v for v in vals if v is None or v >= 0]  # IG hidden likes come back as -1
    return sum(v or 0 for v in vals)


def pct_rank(value, dist):
    if value is None or not dist:
        return None
    pts = [(10, dist["p10"]), (25, dist["p25"]), (50, dist["p50"]), (75, dist["p75"]), (90, dist["p90"])]
    if value <= pts[0][1]:
        return 5
    if value >= pts[-1][1]:
        return 95
    for (p1, v1), (p2, v2) in zip(pts, pts[1:]):
        if v1 <= value <= v2:
            return round(p1 + (p2 - p1) * ((value - v1) / (v2 - v1) if v2 > v1 else 0))
    return None


def between(value, bad, good):
    """0 = at the median bad profile, 1 = at (or beyond) the median good profile. Log scale for ratios."""
    if value is None or bad is None or good is None or value <= 0 or bad <= 0 or good <= 0 or bad == good:
        return None
    x = (math.log(value) - math.log(bad)) / (math.log(good) - math.log(bad))
    return round(max(0.0, min(1.0, x)), 2)


def tier_of(f):
    if f is None:
        return None
    return "2k-10k" if f < 10000 else "10k-50k" if f < 50000 else "50k-150k"


def gmean_rel(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return round(2 ** st.mean(math.log2(max(v, 0) + 0.05) for v in vals), 2)


def spearman(xs, ys):
    if len(xs) < 4:
        return None
    def rank(a):
        o = sorted(range(len(a)), key=lambda i: a[i])
        r = [0.0] * len(a)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and a[o[j + 1]] == a[o[i]]:
                j += 1
            for k in range(i, j + 1):
                r[o[k]] = (i + j) / 2
            i = j + 1
        return r
    rx, ry = rank(xs), rank(ys)
    mx, my = st.mean(rx), st.mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return round(num / den, 2) if den else None


def classify_comment_heuristic(t):
    s = (t or "").strip()
    low = s.lower().strip(" !.🔥❤️👏🙌")
    if not s or EMOJI_RE.match(s):
        return "emoji_only"
    if SPAM_RE.search(s):
        return "spam"
    if CTA_KEYWORD_RE.match(s):
        return "cta_keyword"
    if low in GENERIC or (len(low.split()) <= 3 and not QUESTION_RE.search(s)):
        return "generic"
    if QUESTION_RE.search(s):
        return "question"
    return "substantive"


def bucket_duration(d):
    if d is None:
        return None
    for hi, name in ((60, "<1 min"), (180, "1-3 min"), (480, "3-8 min"), (900, "8-15 min"), (1800, "15-30 min")):
        if d <= hi:
            return name
    return "30 min+"


def bucket_words(n):
    return "<15 words" if n < 15 else "15-40 words" if n <= 40 else "41-80 words" if n <= 80 else "80+ words"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--window-days", type=int, default=90)
    ap.add_argument("--min-age-hours", type=int, default=48)
    ap.add_argument("--peers", help="peer reference json from peer_benchmark.py (creator's own niche)")
    a = ap.parse_args()
    P = lambda n: os.path.join(a.dir, n)
    prof = json.load(open(P("profile.json")))
    posts = json.load(open(P("posts.json")))
    comments = json.load(open(P("comments.json"))) if os.path.exists(P("comments.json")) else []
    engagers = json.load(open(P("engagers.json"))) if os.path.exists(P("engagers.json")) else []
    plat = prof["platform"].lower()
    PN = PLAT_NAME[plat]
    followers = prof.get("followers")
    now = parse_dt(prof.get("fetched_at")) or datetime.now(timezone.utc)

    # ---------------------------------------------------------------- sample
    all_dated = [p for p in posts if parse_dt(p.get("date"))]
    last_post = max((parse_dt(p["date"]) for p in all_dated), default=None)
    sample, excluded = [], Counter()
    for p in posts:
        d = parse_dt(p.get("date"))
        if p.get("pinned"):
            excluded["pinned"] += 1
            continue
        if d and now - d < timedelta(hours=a.min_age_hours):
            excluded["too_new"] += 1
            continue
        if d and now - d > timedelta(days=a.window_days):
            excluded["older_than_window"] += 1
            continue
        if plat == "youtube" and (p.get("views") or 0) >= 1000 and (p.get("likes") or 0) == 0:
            excluded["youtube_hidden_likes"] += 1
            continue
        e = eng_of(p, plat)
        if e is None:
            excluded["no_engagement_data"] += 1
            continue
        p["_eng"] = e
        sample.append(p)
    if len(sample) < 6:
        extra = sorted([p for p in posts if not p.get("pinned") and eng_of(p, plat) is not None and "_eng" not in p],
                       key=lambda p: parse_dt(p.get("date")) or now, reverse=True)
        for p in extra[: 12 - len(sample)]:
            p["_eng"] = eng_of(p, plat)
            sample.append(p)
        excluded["window_fallback_used"] = 1
    sample.sort(key=lambda p: parse_dt(p.get("date")) or now)

    engs = [p["_eng"] for p in sample]
    views = [p["views"] for p in sample if p.get("views") is not None]
    m = {"data_source": prof.get("data_source") or "Apify scrape", "collected_at": prof.get("fetched_at"),
         "platform": PN, "handle": prof.get("handle"), "name": prof.get("name"), "followers": followers,
         "tier": tier_of(followers), "is_business_account": prof.get("is_business"),
         "sample_posts": len(sample), "excluded": dict(excluded),
         "days_since_last_post": round((now - last_post).total_seconds() / 86400, 1) if last_post else None}
    med = st.median(engs) if engs else None
    if engs:
        avg = st.mean(engs)
        m.update({
            "median_engagement": med, "avg_engagement": round(avg, 1),
            "avg_to_median_ratio": round(avg / med, 2) if med else None,
            "median_er_pct": round(med / followers * 100, 3) if followers else None,
            "avg_er_pct": round(avg / followers * 100, 3) if followers else None,
            "best_post_share_pct": round(max(engs) / sum(engs) * 100, 1) if sum(engs) else None,
            "posts_below_half_median_pct": round(sum(1 for e in engs if e < med / 2) / len(engs) * 100, 1),
            "avg_engagement_without_top2": round(st.mean(sorted(engs)[:-2]), 1) if len(engs) > 4 else None,
        })
        top = max(sample, key=lambda p: p["_eng"])
        low = min(sample, key=lambda p: p["_eng"])
        m["best_post"] = {"url": top.get("url"), "engagement": top["_eng"], "views": top.get("views"), "format": top.get("format")}
        m["worst_post"] = {"url": low.get("url"), "engagement": low["_eng"], "views": low.get("views"), "format": low.get("format")}
        tot = sum(engs) or 1
        m["engagement_mix_pct"] = {f: round(sum((p.get(f) or 0) for p in sample) / tot * 100, 1)
                                   for f in ENG_FIELDS[plat]}
    if views:
        m["median_views"] = st.median(views)
        m["avg_views"] = round(st.mean(views), 1)
        m["median_views_to_followers"] = round(st.median(views) / followers, 3) if followers else None
        tv = sum(views)
        te = sum(p["_eng"] for p in sample if p.get("views") is not None)
        m["er_by_views_pct"] = round(te / tv * 100, 3) if tv else None

    # ---------------------------------------------------------------- frequency vs engagement
    dts = [parse_dt(p["date"]) for p in sample if parse_dt(p.get("date"))]
    fq = {}
    if len(dts) >= 2 and (dts[-1] - dts[0]).total_seconds() > 0:
        span_days = (dts[-1] - dts[0]).total_seconds() / 86400
        m["posts_per_week"] = round((len(dts) - 1) / span_days * 7, 2)
        gaps = [(b - a_).total_seconds() / 86400 for a_, b in zip(dts, dts[1:])]
        m["max_gap_days"] = round(max(gaps), 1)
        prof_b = BENCH["profiles"][PN]
        lo, hi = prof_b["sweet_spot_posts_per_week"]
        band = next((b for b in prof_b["frequency_bands"]
                     if b["ppw_from"] <= m["posts_per_week"] < (b["ppw_to"] or 1e9)), None)
        fq["sweet_spot_posts_per_week"] = [lo, hi]
        fq["in_sweet_spot"] = lo <= m["posts_per_week"] <= hi
        fq["above_danger_level"] = m["posts_per_week"] > prof_b["danger_posts_per_week"]
        fq["research_band"] = band
        if med:
            rel = {id(p): p["_eng"] / med for p in sample}
            weeks = defaultdict(list)
            for p in sample:
                d = parse_dt(p.get("date"))
                if d:
                    weeks[d.isocalendar()[:2]].append(rel[id(p)])
            wk = [(len(v), st.median(v)) for v in weeks.values()]
            fq["weeks_observed"] = len(wk)
            fq["spearman_posts_in_week_vs_median_engagement"] = spearman([x for x, _ in wk], [y for _, y in wk])
            close, spaced = [], []
            for prev, p in zip(sample, sample[1:]):
                d0, d1 = parse_dt(prev.get("date")), parse_dt(p.get("date"))
                if d0 and d1:
                    (close if (d1 - d0).total_seconds() < 6 * 3600 else spaced).append(rel[id(p)])
            fq["posts_within_6h_of_previous"] = {"n": len(close), "rel_engagement": gmean_rel(close)}
            fq["posts_spaced_6h_plus"] = {"n": len(spaced), "rel_engagement": gmean_rel(spaced)}
    m["frequency"] = fq

    # ---------------------------------------------------------------- trend
    if med and dts:
        cut = now - timedelta(days=30)
        recent = [p["_eng"] for p in sample if (parse_dt(p.get("date")) or now) >= cut]
        older = [p["_eng"] for p in sample if (parse_dt(p.get("date")) or now) < cut]
        if len(recent) >= 3 and len(older) >= 3 and st.median(older):
            m["trend_last30_vs_before"] = round(st.median(recent) / st.median(older), 2)
        rv = [p["views"] for p in sample if p.get("views") is not None and (parse_dt(p.get("date")) or now) >= cut]
        ov = [p["views"] for p in sample if p.get("views") is not None and (parse_dt(p.get("date")) or now) < cut]
        if len(rv) >= 3 and len(ov) >= 3 and st.median(ov):
            m["views_trend_last30_vs_before"] = round(st.median(rv) / st.median(ov), 2)

    # ---------------------------------------------------------------- what content performs best
    groups = defaultdict(lambda: defaultdict(list))
    sponsored_posts = []
    for prev, p in zip([None] + sample[:-1], sample):
        if not med:
            break
        r = p["_eng"] / med
        cap = p.get("caption") or ""
        groups["format"][p.get("format") or p.get("type") or "unknown"].append(r)
        b = bucket_duration(p.get("duration_s")) if p.get("duration_s") else None
        if b:
            groups["duration"][b].append(r)
        groups["caption_length"][bucket_words(len(cap.split()))].append(r)
        nh = len(re.findall(r"#\w+", cap))
        groups["hashtags"]["0" if nh == 0 else "1-2" if nh <= 2 else "3-5" if nh <= 5 else "6+"].append(r)
        is_sp = bool(p.get("sponsored_flag")) or bool(SPONSOR_RE.search(cap))
        p["_sponsored"] = is_sp
        groups["sponsored"]["sponsored/brand deal" if is_sp else "organic"].append(r)
        if is_sp:
            sponsored_posts.append(p)
        d = parse_dt(p.get("date"))
        if d:
            groups["weekday"][d.strftime("%a")].append(r)
    bd = {}
    for dim, gs in groups.items():
        rows = [{"group": k, "n": len(v), "rel_to_own_median": gmean_rel(v)} for k, v in gs.items()]
        rows.sort(key=lambda x: -(x["rel_to_own_median"] or 0))
        bd[dim] = rows
    m["content_breakdown"] = bd
    m["content_breakdown_note"] = ("rel_to_own_median = geometric-mean engagement of that group vs the creator's median "
                                   "post (1.0 = typical). Groups with n<3 are anecdotes.")
    rank = [p for p in sample]
    rank.sort(key=lambda p: -p["_eng"])
    m["top_posts"] = [{"url": p.get("url"), "rel": round(p["_eng"] / med, 2) if med else None, "format": p.get("format"),
                       "caption": (p.get("caption") or "")[:160]} for p in rank[:5]]
    m["bottom_posts"] = [{"url": p.get("url"), "rel": round(p["_eng"] / med, 2) if med else None, "format": p.get("format"),
                          "caption": (p.get("caption") or "")[:160]} for p in rank[-3:]]

    # ---------------------------------------------------------------- brands in content
    own = (prof.get("handle") or "").lower().lstrip("@")
    brand_posts = defaultdict(set)
    for p in sample:
        cap = p.get("caption") or ""
        names = set(x.lower().rstrip(".") for x in MENTION_RE.findall(cap))
        for extra in (p.get("mentions") or []) + (p.get("tagged") or []):
            if isinstance(extra, str):
                names.add(extra.lower().lstrip("@"))
        for dmn in DOMAIN_RE.findall(cap):
            dmn = dmn.lower()
            if dmn not in LINK_HOSTS_IGNORE:
                names.add("site:" + dmn)
        for c in CODE_RE.findall(cap):
            names.add("code:" + c)
        names.discard(own)
        for n in names:
            brand_posts[n].add(p.get("url"))
    m["brands"] = {
        "sponsored_posts": len(sponsored_posts),
        "sponsored_share_pct": round(len(sponsored_posts) / len(sample) * 100, 1) if sample else None,
        "sponsored_rel_to_own_median": gmean_rel([p["_eng"] / med for p in sponsored_posts]) if med and sponsored_posts else None,
        "sponsored_post_urls": [p.get("url") for p in sponsored_posts][:10],
        "mention_candidates": sorted([{"name": k, "posts": len(v)} for k, v in brand_posts.items()],
                                     key=lambda x: -x["posts"])[:40],
        "note": "Candidates are raw @mentions, tagged accounts, linked domains and discount codes. "
                "The model decides which are brands, which are competitors, and which are just people.",
    }

    # ---------------------------------------------------------------- references
    pb = BENCH["platforms"][PN]
    tb = pb["tiers"].get(m["tier"]) if m["tier"] else None
    bm = tb or pb["all"]
    m["niche_reference"] = {
        "group": f"AI/marketing creators, {PN} {m['tier'] or 'all tiers'}",
        "percentiles": {
            "median_er": pct_rank(m.get("median_er_pct"), bm.get("median_er_pct")),
            "median_views_to_followers": pct_rank(m.get("median_views_to_followers"), bm.get("median_views_to_followers")),
            "er_by_views": pct_rank(m.get("er_by_views_pct"), bm.get("er_by_views_pct")),
        },
        "medians": {k: (v or {}).get("p50") for k, v in bm.items()},
    }
    if a.peers:
        peers = json.load(open(a.peers))
        m["niche_reference"] = {
            "group": peers.get("group", "peer set"),
            "percentiles": {k: pct_rank(m.get(f), peers.get(f)) for k, f in
                            (("median_er", "median_er_pct"), ("median_views_to_followers", "median_views_to_followers"),
                             ("er_by_views", "er_by_views_pct"))},
            "medians": {k: (v or {}).get("p50") for k, v in peers.items() if isinstance(v, dict)},
            "peer_file": a.peers,
        }
    good, bad = BENCH["profiles"][PN]["good"], BENCH["profiles"][PN]["bad"]
    cshare = m.get("engagement_mix_pct", {}).get("comments")
    m["profile_position"] = {
        "_meaning": "0 = like the median BAD profile on this platform, 1 = like the median GOOD profile (niche-agnostic)",
        "consistency_avg_to_median": between(1 / m["avg_to_median_ratio"] if m.get("avg_to_median_ratio") else None,
                                             1 / bad["avg_to_median"], 1 / good["avg_to_median"]),
        "best_post_share": between(1 / m["best_post_share_pct"] if m.get("best_post_share_pct") else None,
                                   1 / bad["best_post_share_pct"], 1 / good["best_post_share_pct"]),
        "views_to_followers": between(m.get("median_views_to_followers"), bad.get("median_views_to_followers"),
                                      good.get("median_views_to_followers")),
        "comment_share_of_engagement": between(cshare, bad.get("comments_share_of_engagement_pct"),
                                               good.get("comments_share_of_engagement_pct")) if PN in ("Instagram", "YouTube", "X") else None,
        "good_profile_medians": good, "bad_profile_medians": bad,
    }

    # ---------------------------------------------------------------- comments
    cm = [c for c in comments if (c.get("author") or "").lower() != own]
    kinds = Counter(classify_comment_heuristic(c.get("text")) for c in cm)
    texts = Counter(re.sub(r"\W+", " ", (c.get("text") or "").lower()).strip() for c in cm)
    dup = sum(n for t, n in texts.items() if t and n >= 3)
    authors = Counter(c["author"] for c in cm)
    posts_with_comments = len({c.get("post_url") for c in cm if c.get("post_url")}) or 1
    per_author_posts = Counter({au: len({c.get("post_url") for c in cm if c["author"] == au}) for au in authors})
    repeaters = [au for au, n in per_author_posts.items() if posts_with_comments >= 4 and n >= max(3, posts_with_comments * 0.5)]
    n = len(cm) or 1
    m["comments"] = {
        "sampled": len(cm), "unique_authors": len(authors),
        "share_pct": {k: round(v / n * 100, 1) for k, v in kinds.items()},
        "duplicate_text_share_pct": round(dup / n * 100, 1),
        "repeat_commenters": len(repeaters),
        "repeat_commenters_share_of_authors_pct": round(len(repeaters) / max(1, len(authors)) * 100, 1),
        "creator_replies": sum(1 for c in comments if (c.get("author") or "").lower() == own),
    }

    # ---------------------------------------------------------------- engager bot heuristics
    sus = with_prof = 0
    for e in engagers:
        if any(k in e for k in ("followers", "following", "posts")):
            with_prof += 1
            fol, fng, pst = e.get("followers"), e.get("following"), e.get("posts")
            flags = []
            if pst is not None and pst == 0:
                flags.append("no posts")
            if fol is not None and fng is not None and fng > 1000 and fol < fng * 0.05:
                flags.append("follows many, followed by few")
            if not e.get("bio") and (fol or 0) < 20:
                flags.append("empty bio, <20 followers")
            if re.search(r"\d{5,}$", e.get("author") or ""):
                flags.append("handle ends in long digit string")
            e["bot_signals"] = flags
            sus += len(flags) >= 2
    m["engagers"] = {"total": len(engagers), "with_bio": sum(1 for e in engagers if e.get("bio")),
                     "with_profile_stats": with_prof, "bot_suspect_heuristic": sus,
                     "bot_suspect_share_pct": round(sus / with_prof * 100, 1) if with_prof else None}

    # ---------------------------------------------------------------- flags
    fl = []
    r = m.get("avg_to_median_ratio")
    if r and r >= 5:
        fl.append(("NO_GO", "viral_skew", f"Average engagement is {r}x the median: a few viral posts carry the account."))
    elif r and r >= 3:
        fl.append(("WARN", "viral_skew_moderate", f"Average engagement is {r}x the median (healthy accounts: 1.2-1.6x)."))
    if (m.get("best_post_share_pct") or 0) >= 50:
        fl.append(("NO_GO", "one_hit", f"Best post holds {m['best_post_share_pct']}% of all sampled engagement."))
    if (m.get("posts_per_week") or 0) >= 21 and (m.get("median_er_pct") or 0) < 0.1:
        fl.append(("NO_GO", "bulk_posting", "21+ posts/week with median ER below 0.1%: likely automated or bulk posting."))
    if m["engagers"]["bot_suspect_share_pct"] is not None and m["engagers"]["bot_suspect_share_pct"] >= 30 \
            and m["engagers"]["with_profile_stats"] >= 30:
        fl.append(("NO_GO", "bot_engagers", f"{m['engagers']['bot_suspect_share_pct']}% of checked engagers look like bots."))
    vf = m.get("median_views_to_followers")
    if vf is not None and plat != "linkedin" and vf < 0.05 and (followers or 0) >= 5000:
        fl.append(("WARN", "dead_followers", f"Median post reaches {vf}x followers (bad-profile signature <0.05x; "
                   f"good profiles ~{good.get('median_views_to_followers')}x): follower base inactive or bought."))
    if fq.get("above_danger_level"):
        fl.append(("WARN", "over_posting", f"{m['posts_per_week']} posts/week is above the level where engagement "
                   f"collapses on {PN} (>{BENCH['profiles'][PN]['danger_posts_per_week']}/week)."))
    sp = fq.get("spearman_posts_in_week_vs_median_engagement")
    if sp is not None and sp <= -0.5 and fq.get("weeks_observed", 0) >= 5:
        fl.append(("WARN", "frequency_dilution", f"Per-post engagement falls in busier weeks (rank corr {sp}): "
                   "more posts split the same audience."))
    tr = m.get("trend_last30_vs_before")
    if tr is not None and tr < 0.6:
        fl.append(("WARN", "declining", f"Last 30 days median engagement is {tr}x the earlier median."))
    junk = sum(m["comments"]["share_pct"].get(k, 0) for k in ("emoji_only", "spam"))
    if m["comments"]["sampled"] >= 40 and (junk >= 50 or m["comments"]["duplicate_text_share_pct"] >= 25):
        fl.append(("WARN", "low_quality_comments", f"{round(junk)}% emoji/spam comments, "
                   f"{m['comments']['duplicate_text_share_pct']}% duplicate texts."))
    if m["comments"]["sampled"] >= 40 and m["comments"]["share_pct"].get("cta_keyword", 0) >= 40:
        fl.append(("WARN", "comment_bait", "Most comments are one-word keyword replies (comment-to-get-link); "
                   "engagement is inflated by the CTA."))
    if m["comments"]["repeat_commenters_share_of_authors_pct"] >= 20 and m["comments"]["unique_authors"] >= 15:
        fl.append(("WARN", "engagement_pod", f"{m['comments']['repeat_commenters']} accounts comment on most posts: possible pod."))
    if (m["brands"]["sponsored_share_pct"] or 0) >= 30 and len(sample) >= 8:
        fl.append(("WARN", "ad_heavy", f"{m['brands']['sponsored_share_pct']}% of recent posts are brand deals: ad-fatigued audience."))
    srel = m["brands"]["sponsored_rel_to_own_median"]
    if srel is not None and srel < 0.5 and m["brands"]["sponsored_posts"] >= 2:
        fl.append(("WARN", "sponsored_underperform", f"Their sponsored posts get {srel}x their typical engagement."))
    if m.get("is_business_account"):
        fl.append(("WARN", "business_account", "Business/brand account: in the research these engage far below personal "
                   "creator accounts. Confirm it is a real person."))
    if (m.get("days_since_last_post") or 0) > 45:
        fl.append(("WARN", "inactive", f"No post in {m['days_since_last_post']} days."))
    if (m.get("posts_per_week") or 99) < 0.5 and plat != "youtube":
        fl.append(("WARN", "low_frequency", "Less than one post every two weeks."))
    if len(sample) < 10:
        fl.append(("WARN", "small_sample", f"Only {len(sample)} posts in the sample: lower confidence."))
    if not followers:
        fl.append(("WARN", "no_followers", "Follower count missing: ER cannot be computed."))
    m["flags"] = [{"level": l, "code": c, "detail": d} for l, c, d in fl]
    json.dump(m, open(P("metrics.json"), "w"), indent=1, default=str)

    # ---------------------------------------------------------------- hand-off for judgment pass
    tc = {
        "creator_bio": prof.get("bio"), "creator_name": prof.get("name"),
        "posts": [{"url": p.get("url"), "date": p.get("date"), "format": p.get("format"),
                   "rel_to_own_median": round(p["_eng"] / med, 2) if med else None, "views": p.get("views"),
                   "sponsored_detected": p.get("_sponsored"), "caption": (p.get("caption") or "")[:1200],
                   "transcript": p.get("transcript") if isinstance(p.get("transcript"), str) else None}
                  for p in reversed(sample)],
        "brand_mention_candidates": m["brands"]["mention_candidates"],
        "engagers": [{"author": e["author"], "bio": (e.get("bio") or "")[:300],
                      "sample_comment": (e.get("comments") or [""])[0][:200],
                      "reactions": e.get("reactions", 0), "bot_signals": e.get("bot_signals", [])}
                     for e in engagers if (e.get("author") or "").lower() != own],
        "comments": [{"i": i, "author": c["author"], "text": (c.get("text") or "")[:300],
                      "heuristic": classify_comment_heuristic(c.get("text"))} for i, c in enumerate(cm)],
    }
    json.dump(tc, open(P("to_classify.json"), "w"), indent=1, default=str)
    print(json.dumps({k: m.get(k) for k in ("platform", "handle", "followers", "sample_posts", "median_er_pct",
                                            "avg_to_median_ratio", "median_views_to_followers", "posts_per_week",
                                            "trend_last30_vs_before")}, indent=1))
    for f in m["flags"]:
        print(f"[{f['level']}] {f['code']}: {f['detail']}")


if __name__ == "__main__":
    main()
