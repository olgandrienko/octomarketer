#!/usr/bin/env python3
"""
Pull everything needed to validate one creator account via Apify, and write it
in a normalized shape that compute_metrics.py understands.

Usage:
  python apify_fetch.py --url https://www.tiktok.com/@someuser --out ./runs/someuser_tiktok
  python apify_fetch.py --platform linkedin --handle someone --out ./runs/someone_linkedin
  (--url auto-detects the platform from instagram.com / tiktok.com / youtube.com / linkedin.com / x.com / twitter.com)

Needs APIFY_TOKEN in the environment (or in a .env file in the current dir).

Stages (each saves raw/*.json so a failed stage can be re-run with --only):
  posts      -> recent posts + profile (followers, bio)
  comments   -> comments on a spread of recent posts (not just the viral one)
  reactions  -> LinkedIn only: who reacted (with headlines) - best ICP signal
  profiles   -> bios of commenters where the comment payload has no bio (IG, TikTok)

Output files in --out:
  profile.json, posts.json, comments.json, engagers.json, fetch_log.json, raw/

Actor input schemas change from time to time. If a run fails or returns 0 items,
run with --show-input to print the input that was sent, compare with the actor's
current input schema in the Apify console, and pass an override with
--input-override '{"stage": {...extra or replacement keys...}}'.
"""
import argparse, json, os, re, ssl, sys, time, urllib.request, urllib.parse, urllib.error
from datetime import datetime, timezone

API = "https://api.apify.com/v2"

ACTORS = {
    "instagram": {"posts": "apify/instagram-scraper", "profile": "apify/instagram-profile-scraper",
                   "comments": "apify/instagram-comment-scraper", "profiles": "apify/instagram-profile-scraper"},
    "tiktok": {"posts": "clockworks/tiktok-scraper", "comments": "clockworks/tiktok-comments-scraper",
               "profiles": "clockworks/tiktok-profile-scraper"},
    "youtube": {"posts": "streamers/youtube-scraper", "comments": "streamers/youtube-comments-scraper"},
    "linkedin": {"posts": "harvestapi/linkedin-profile-posts", "profile": "harvestapi/linkedin-profile-scraper",
                  "comments": "harvestapi/linkedin-post-comments", "reactions": "harvestapi/linkedin-post-reactions"},
    "x": {"posts": "apidojo/tweet-scraper", "comments": "apidojo/tweet-scraper"},
}


# ---------------------------------------------------------------- utilities
def load_token():
    tok = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    if not tok and os.path.exists(".env"):
        for line in open(".env"):
            m = re.match(r"\s*APIFY(?:_API)?_TOKEN\s*=\s*(.+)", line)
            if m:
                tok = m.group(1).strip().strip('"').strip("'")
    if not tok:
        sys.exit("APIFY_TOKEN not found. Set it in the environment or a .env file "
                 "(get one at https://console.apify.com/settings/integrations).")
    return tok


def ssl_ctx():
    ca = os.environ.get("SSL_CERT_FILE") or os.environ.get("REQUESTS_CA_BUNDLE")
    if not ca and os.path.exists("/root/.ccr/ca-bundle.crt"):
        ca = "/root/.ccr/ca-bundle.crt"
    return ssl.create_default_context(cafile=ca) if ca else ssl.create_default_context()


def http(method, url, body=None, timeout=120):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx()) as r:
        return json.loads(r.read().decode() or "null")


def run_actor(token, actor, inp, log, max_wait=900, show=False):
    if show:
        print(f"\n>>> {actor} input:\n{json.dumps(inp, indent=1)}")
    aid = actor.replace("/", "~")
    t0 = time.time()
    try:
        run = http("POST", f"{API}/acts/{aid}/runs?token={token}", inp)["data"]
    except urllib.error.HTTPError as e:
        msg = e.read().decode()[:500]
        log.append({"actor": actor, "status": "START_FAILED", "error": msg})
        print(f"[!] {actor} failed to start: {msg}", file=sys.stderr)
        return []
    rid = run["id"]
    status = run["status"]
    while status in ("READY", "RUNNING") and time.time() - t0 < max_wait:
        time.sleep(5)
        run = http("GET", f"{API}/actor-runs/{rid}?token={token}")["data"]
        status = run["status"]
    if status in ("READY", "RUNNING"):
        http("POST", f"{API}/actor-runs/{rid}/abort?token={token}")
        status = "ABORTED_TIMEOUT"
    items = http("GET", f"{API}/datasets/{run['defaultDatasetId']}/items?token={token}&clean=true&format=json",
                 timeout=300) or []
    cost = (run.get("usageTotalUsd") or 0)
    log.append({"actor": actor, "run_id": rid, "status": status, "items": len(items),
                "usd": round(cost, 4), "seconds": round(time.time() - t0)})
    print(f"[ok] {actor}: {status}, {len(items)} items, ${cost:.3f}", file=sys.stderr)
    return items


def g(d, *paths, default=None):
    """Get first non-empty value among dotted paths."""
    for p in paths:
        cur = d
        ok = True
        for k in p.split("."):
            if isinstance(cur, dict) and k in cur and cur[k] is not None:
                cur = cur[k]
            else:
                ok = False
                break
        if ok and cur != "":
            return cur
    return default


def num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        if isinstance(v, str):
            s = v.replace(",", "").strip().upper()
            m = re.match(r"([\d.]+)\s*([KMB])?", s)
            if m:
                mult = {"K": 1e3, "M": 1e6, "B": 1e9}.get(m.group(2), 1)
                return float(m.group(1)) * mult
        return None


def iso(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        v = v / 1000 if v > 1e11 else v
        return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
    s = str(v)
    for fmt in ("%a %b %d %H:%M:%S %z %Y",):
        try:
            return datetime.strptime(s, fmt).isoformat()
        except ValueError:
            pass
    return s


def handle_of(platform, h):
    h = h.strip()
    if platform == "linkedin":
        return h if h.startswith("http") else f"https://www.linkedin.com/in/{h.strip('/')}"
    if h.startswith("http"):
        path = urllib.parse.urlparse(h).path.strip("/").split("/")
        h = path[-1] if path else h
    return h.lstrip("@")


# ---------------------------------------------------------------- per platform
def fetch_posts(platform, handle, n, token, log, ov, show):
    profile, posts = {}, []
    if platform == "instagram":
        url = f"https://www.instagram.com/{handle}/"
        items = run_actor(token, ACTORS[platform]["posts"],
                          {"directUrls": [url], "resultsType": "posts", "resultsLimit": n, "addParentData": False,
                           **ov.get("posts", {})}, log, show=show)
        prof = run_actor(token, ACTORS[platform]["profile"], {"usernames": [handle], **ov.get("profile", {})},
                         log, show=show)
        p = prof[0] if prof else {}
        profile = {"followers": num(g(p, "followersCount")), "bio": g(p, "biography", default=""),
                   "name": g(p, "fullName"), "url": url, "external_url": g(p, "externalUrl"),
                   "is_business": g(p, "isBusinessAccount"), "verified": g(p, "verified")}
        for it in items:
            posts.append({"id": g(it, "id", "shortCode"), "url": g(it, "url"),
                          "date": iso(g(it, "timestamp")), "type": g(it, "type", "productType"),
                          "views": num(g(it, "videoPlayCount", "videoViewCount", "igPlayCount")),
                          "likes": num(g(it, "likesCount")), "comments": num(g(it, "commentsCount")),
                          "shares": None, "saves": None, "pinned": bool(g(it, "isPinned", default=False)),
                          "caption": g(it, "caption", default=""), "duration_s": num(g(it, "videoDuration")),
                          "sponsored_flag": bool(g(it, "isSponsored", "paidPartnership", default=False)),
                          "tagged": [t.get("username") for t in (g(it, "taggedUsers", default=[]) or []) if isinstance(t, dict)],
                          "mentions": g(it, "mentions", default=[]),
                          "format": {"Video": "reel/video", "Sidecar": "carousel", "Image": "image"}.get(g(it, "type"), g(it, "type"))})
    elif platform == "tiktok":
        items = run_actor(token, ACTORS[platform]["posts"],
                          {"profiles": [handle], "resultsPerPage": n, "profileScrapeSections": ["videos"],
                           "shouldDownloadVideos": False, "shouldDownloadCovers": False,
                           "shouldDownloadSubtitles": True, **ov.get("posts", {})}, log, show=show)
        if items:
            a = g(items[0], "authorMeta", default={})
            profile = {"followers": num(g(a, "fans")), "bio": g(a, "signature", default=""),
                       "name": g(a, "nickName", "name"), "url": f"https://www.tiktok.com/@{handle}",
                       "verified": g(a, "verified"), "external_url": g(a, "bioLink.link"),
                       "is_business": g(a, "commerceUserInfo.commerceUser", "ttSeller")}
        for it in items:
            posts.append({"id": g(it, "id"), "url": g(it, "webVideoUrl"), "date": iso(g(it, "createTimeISO", "createTime")),
                          "type": "slideshow" if g(it, "isSlideshow") else "video",
                          "views": num(g(it, "playCount")), "likes": num(g(it, "diggCount")),
                          "comments": num(g(it, "commentCount")), "shares": num(g(it, "shareCount")),
                          "saves": num(g(it, "collectCount")), "pinned": bool(g(it, "isPinned", default=False)),
                          "caption": g(it, "text", default=""), "duration_s": num(g(it, "videoMeta.duration")),
                          "transcript": g(it, "subtitles", "videoMeta.subtitleLinks"),
                          "sponsored_flag": bool(g(it, "isAd", "isSponsored", default=False)),
                          "mentions": g(it, "mentions", default=[]),
                          "format": "slideshow" if g(it, "isSlideshow") else "video"})
    elif platform == "youtube":
        url = handle if handle.startswith("http") else f"https://www.youtube.com/@{handle}"
        items = run_actor(token, ACTORS[platform]["posts"],
                          {"startUrls": [{"url": url}], "maxResults": n, "maxResultsShorts": max(5, n // 3),
                           "maxResultStreams": 0, **ov.get("posts", {})}, log, show=show)
        if items:
            it0 = items[0]
            profile = {"followers": num(g(it0, "numberOfSubscribers", "channelSubscribers", "aboutChannelInfo.numberOfSubscribers")),
                       "bio": g(it0, "channelDescription", "aboutChannelInfo.channelDescription", default=""),
                       "name": g(it0, "channelName"), "url": g(it0, "channelUrl", default=url)}
        for it in items:
            if g(it, "type") == "channel" and not g(it, "viewCount"):
                continue
            posts.append({"id": g(it, "id"), "url": g(it, "url"), "date": iso(g(it, "date", "uploadDate")),
                          "type": "short" if "/shorts/" in str(g(it, "url", default="")) else "video",
                          "views": num(g(it, "viewCount")), "likes": num(g(it, "likes")),
                          "comments": num(g(it, "commentsCount")), "shares": None, "saves": None, "pinned": False,
                          "caption": (g(it, "title", default="") + "\n" + str(g(it, "text", default="")))[:3000],
                          "duration_s": dur_s(g(it, "duration")),
                          "format": "short" if "/shorts/" in str(g(it, "url", default="")) else "long-form video",
                          "sponsored_flag": bool(g(it, "isPaidPromotion", "hasPaidProductPlacement", default=False))})
    elif platform == "linkedin":
        items = run_actor(token, ACTORS[platform]["posts"],
                          {"targetUrls": [handle], "maxPosts": n, "includeReposts": False,
                           "includeQuotePosts": True, **ov.get("posts", {})}, log, show=show)
        prof = run_actor(token, ACTORS[platform]["profile"], {"urls": [handle], "queries": [handle],
                         **ov.get("profile", {})}, log, show=show)
        p = prof[0] if prof else {}
        profile = {"followers": num(g(p, "followerCount", "followersCount", "followers")),
                   "bio": (str(g(p, "headline", default="")) + "\n" + str(g(p, "about", "summary", default=""))).strip(),
                   "name": " ".join(filter(None, [g(p, "firstName"), g(p, "lastName")])) or g(p, "fullName"),
                   "url": handle, "connections": num(g(p, "connectionsCount", "connections"))}
        for it in items:
            if g(it, "type") == "repost" or g(it, "repostedBy"):
                continue
            posts.append({"id": g(it, "id", "entityId"), "url": g(it, "linkedinUrl", "url"),
                          "date": iso(g(it, "postedAt.timestamp", "postedAt.date", "postedAtISO")),
                          "type": g(it, "type", default="post"), "views": None,
                          "likes": num(g(it, "engagement.likes", "numLikes", "totalReactionCount")),
                          "comments": num(g(it, "engagement.comments", "numComments")),
                          "shares": num(g(it, "engagement.shares", "numShares")), "saves": None, "pinned": False,
                          "caption": g(it, "content", "text", default=""),
                          "format": li_format(it)})
    elif platform == "x":
        items = run_actor(token, ACTORS[platform]["posts"],
                          {"searchTerms": [f"from:{handle} -filter:replies -filter:retweets"], "maxItems": n,
                           "sort": "Latest", **ov.get("posts", {})}, log, show=show)
        if items:
            a = g(items[0], "author", default={})
            profile = {"followers": num(g(a, "followers", "followersCount")), "bio": g(a, "description", default=""),
                       "name": g(a, "name"), "url": f"https://x.com/{handle}", "verified": g(a, "isBlueVerified")}
        for it in items:
            if g(it, "isRetweet") or g(it, "isReply"):
                continue
            posts.append({"id": g(it, "id"), "url": g(it, "url", "twitterUrl"), "date": iso(g(it, "createdAt")),
                          "type": "tweet", "views": num(g(it, "viewCount")), "likes": num(g(it, "likeCount")),
                          "comments": num(g(it, "replyCount")), "shares": num(g(it, "retweetCount")),
                          "quotes": num(g(it, "quoteCount")), "saves": num(g(it, "bookmarkCount")), "pinned": False,
                          "caption": g(it, "text", "fullText", default=""), "conversation_id": g(it, "conversationId"),
                          "format": x_format(it)})
    return profile, posts


def dur_s(v):
    if v is None:
        return None
    if isinstance(v, (int, float)):
        return float(v)
    parts = [int(x) for x in re.findall(r"\d+", str(v))]
    s = 0
    for p in parts:
        s = s * 60 + p
    return float(s) if parts else None


def li_format(it):
    if g(it, "document") or g(it, "postDocument"):
        return "carousel/document"
    imgs = g(it, "postImages", "images", default=[]) or []
    if g(it, "postVideo", "video"):
        return "video"
    if isinstance(imgs, list) and len(imgs) > 1:
        return "multi-image"
    if imgs:
        return "image"
    if g(it, "poll"):
        return "poll"
    if g(it, "repostedPost", "resharedPost", "quotedPost"):
        return "quote post"
    if g(it, "article", "linkedinArticle"):
        return "article/link"
    return "text"


def x_format(it):
    if g(it, "isQuote") or g(it, "quote"):
        return "quote"
    media = g(it, "extendedEntities.media", "entities.media", "media", default=[]) or []
    kinds = {m.get("type") for m in media if isinstance(m, dict)}
    if kinds & {"video", "animated_gif"}:
        return "video"
    if "photo" in kinds or media:
        return "image"
    return "text"


def detect_platform(url):
    u = url.lower()
    for key, plat in (("instagram.com", "instagram"), ("tiktok.com", "tiktok"), ("youtube.com", "youtube"),
                      ("youtu.be", "youtube"), ("linkedin.com", "linkedin"), ("x.com", "x"), ("twitter.com", "x")):
        if key in u:
            return plat
    return None


def pick_posts_for_comments(posts, k):
    """Spread across the sample: typical posts, not only the best one.
    Skip posts younger than 48h (engagement not settled) and posts with 0 comments."""
    now = datetime.now(timezone.utc)
    cand = []
    for p in posts:
        try:
            d = datetime.fromisoformat(str(p["date"]).replace("Z", "+00:00"))
            if d.tzinfo is None:
                d = d.replace(tzinfo=timezone.utc)
            if (now - d).total_seconds() < 48 * 3600:
                continue
        except Exception:
            pass
        if (p.get("comments") or 0) > 0 and not p.get("pinned"):
            cand.append(p)
    cand.sort(key=lambda p: p.get("comments") or 0)
    if len(cand) <= k:
        return cand
    step = (len(cand) - 1) / (k - 1) if k > 1 else 0
    return [cand[round(i * step)] for i in range(k)]


def fetch_comments(platform, handle, chosen, per_post, token, log, ov, show):
    out = []
    urls = [p["url"] for p in chosen if p.get("url")]
    if not urls:
        return out
    if platform == "instagram":
        items = run_actor(token, ACTORS[platform]["comments"],
                          {"directUrls": urls, "resultsLimit": per_post, **ov.get("comments", {})}, log, show=show)
        for it in items:
            out.append({"post_url": g(it, "postUrl", "inputUrl", "url"), "author": g(it, "ownerUsername", "owner.username"),
                        "author_bio": None, "text": g(it, "text", default=""), "likes": num(g(it, "likesCount")),
                        "is_reply": bool(g(it, "parentId"))})
    elif platform == "tiktok":
        items = run_actor(token, ACTORS[platform]["comments"],
                          {"postURLs": urls, "commentsPerPost": per_post, "maxRepliesPerComment": 0,
                           **ov.get("comments", {})}, log, show=show)
        for it in items:
            out.append({"post_url": g(it, "videoWebUrl", "submittedVideoUrl"), "author": g(it, "uniqueId", "user.uniqueId"),
                        "author_bio": g(it, "user.signature"), "text": g(it, "text", default=""),
                        "likes": num(g(it, "diggCount")), "is_reply": bool(g(it, "repliesToId"))})
    elif platform == "youtube":
        items = run_actor(token, ACTORS[platform]["comments"],
                          {"startUrls": [{"url": u} for u in urls], "maxComments": per_post, "commentsSortBy": "0",
                           **ov.get("comments", {})}, log, show=show)
        for it in items:
            out.append({"post_url": g(it, "pageUrl", "videoUrl"), "author": g(it, "author", "authorName"),
                        "author_bio": None, "text": g(it, "comment", "text", default=""),
                        "likes": num(g(it, "voteCount", "likes")), "is_reply": bool(g(it, "replyToCid"))})
    elif platform == "linkedin":
        items = run_actor(token, ACTORS[platform]["comments"],
                          {"posts": urls, "maxItems": per_post * len(urls), **ov.get("comments", {})}, log, show=show)
        for it in items:
            out.append({"post_url": g(it, "postUrl", "query.post", "post"), "author": g(it, "actor.name", "author.name"),
                        "author_url": g(it, "actor.linkedinUrl", "author.profileUrl"),
                        "author_bio": g(it, "actor.position", "author.headline", "actor.headline"),
                        "text": g(it, "commentary", "text", default=""),
                        "likes": num(g(it, "engagement.likes", "numLikes")), "is_reply": False})
    elif platform == "x":
        terms = [f"conversation_id:{p['conversation_id'] or p['id']}" for p in chosen]
        items = run_actor(token, ACTORS[platform]["comments"],
                          {"searchTerms": terms, "maxItems": per_post * len(terms), "sort": "Latest",
                           **ov.get("comments", {})}, log, show=show)
        conv2url = {str(p.get("conversation_id") or p["id"]): p["url"] for p in chosen}
        for it in items:
            if str(g(it, "author.userName", default="")).lower() == handle.lower():
                continue
            if str(g(it, "id")) in conv2url:
                continue
            out.append({"post_url": conv2url.get(str(g(it, "conversationId")), None),
                        "author": g(it, "author.userName"), "author_bio": g(it, "author.description"),
                        "author_followers": num(g(it, "author.followers")),
                        "text": g(it, "text", default=""), "likes": num(g(it, "likeCount")), "is_reply": True})
    return [c for c in out if c.get("author")]


def fetch_reactions(chosen, per_post, token, log, ov, show):
    urls = [p["url"] for p in chosen if p.get("url")]
    items = run_actor(token, ACTORS["linkedin"]["reactions"],
                      {"posts": urls, "maxItems": per_post * len(urls), **ov.get("reactions", {})}, log, show=show)
    return [{"post_url": g(it, "query.post", "postUrl"), "author": g(it, "actor.name"),
             "author_url": g(it, "actor.linkedinUrl"), "author_bio": g(it, "actor.position", "actor.headline"),
             "reaction": g(it, "reactionType")} for it in items if g(it, "actor.name")]


def fetch_profiles(platform, names, token, log, ov, show):
    if not names:
        return {}
    bios = {}
    if platform == "instagram":
        items = run_actor(token, ACTORS[platform]["profiles"], {"usernames": names, **ov.get("profiles", {})},
                          log, show=show)
        for it in items:
            bios[g(it, "username")] = {"bio": g(it, "biography", default=""), "followers": num(g(it, "followersCount")),
                                       "following": num(g(it, "followsCount")), "posts": num(g(it, "postsCount")),
                                       "name": g(it, "fullName"), "is_private": g(it, "private"),
                                       "is_business": g(it, "isBusinessAccount"), "category": g(it, "businessCategoryName")}
    elif platform == "tiktok":
        items = run_actor(token, ACTORS[platform]["profiles"],
                          {"profiles": names, "resultsPerPage": 1, "shouldDownloadVideos": False,
                           **ov.get("profiles", {})}, log, show=show)
        for it in items:
            a = g(it, "authorMeta", default={})
            bios[g(a, "name", "uniqueId")] = {"bio": g(a, "signature", default=""), "followers": num(g(a, "fans")),
                                              "following": num(g(a, "following")), "posts": num(g(a, "video")),
                                              "name": g(a, "nickName")}
    return bios


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="profile link; platform is detected from it")
    ap.add_argument("--platform", choices=list(ACTORS))
    ap.add_argument("--handle")
    ap.add_argument("--out", required=True)
    ap.add_argument("--posts", type=int, default=25, help="recent posts to sample")
    ap.add_argument("--comment-posts", type=int, default=8, help="posts to pull comments from")
    ap.add_argument("--comments-per-post", type=int, default=40)
    ap.add_argument("--reactions-per-post", type=int, default=60, help="LinkedIn only")
    ap.add_argument("--max-profiles", type=int, default=150, help="engager bios to look up (IG/TikTok)")
    ap.add_argument("--only", choices=["posts", "comments", "reactions", "profiles"], action="append")
    ap.add_argument("--input-override", default="{}", help='JSON: {"posts": {...}, "comments": {...}}')
    ap.add_argument("--show-input", action="store_true")
    a = ap.parse_args()

    plat = a.platform or (detect_platform(a.url) if a.url else None)
    if not plat or not (a.url or a.handle):
        ap.error("give --url (platform auto-detected) or --platform + --handle")
    raw_handle = a.handle or a.url
    if plat == "youtube" and a.url and "/@" not in a.url:
        handle = a.url  # channel/ID URLs are passed through as-is
    else:
        handle = handle_of(plat, raw_handle)
    token = load_token()
    ov = json.loads(a.input_override)
    os.makedirs(os.path.join(a.out, "raw"), exist_ok=True)
    P = lambda name: os.path.join(a.out, name)
    stages = a.only or ["posts", "comments", "reactions", "profiles"]
    logf = P("fetch_log.json")
    log = json.load(open(logf)) if os.path.exists(logf) else []

    if "posts" in stages:
        profile, posts = fetch_posts(plat, handle, a.posts, token, log, ov, a.show_input)
        profile.update({"platform": plat, "handle": handle, "fetched_at": datetime.now(timezone.utc).isoformat()})
        json.dump(profile, open(P("profile.json"), "w"), indent=1)
        json.dump(posts, open(P("posts.json"), "w"), indent=1)
    posts = json.load(open(P("posts.json")))
    chosen = pick_posts_for_comments(posts, a.comment_posts)

    if "comments" in stages:
        comments = fetch_comments(plat, handle, chosen, a.comments_per_post, token, log, ov, a.show_input)
        json.dump(comments, open(P("comments.json"), "w"), indent=1)
    comments = json.load(open(P("comments.json"))) if os.path.exists(P("comments.json")) else []

    reactions = []
    if plat == "linkedin" and "reactions" in stages:
        reactions = fetch_reactions(chosen, a.reactions_per_post, token, log, ov, a.show_input)
        json.dump(reactions, open(P("reactions.json"), "w"), indent=1)
    elif os.path.exists(P("reactions.json")):
        reactions = json.load(open(P("reactions.json")))

    bios = {}
    if "profiles" in stages and plat in ("instagram", "tiktok"):
        own = handle.lower()
        need, seen = [], set()
        for c in comments:
            n = c["author"]
            if n and n.lower() != own and n not in seen and not c.get("author_bio"):
                seen.add(n)
                need.append(n)
        bios = fetch_profiles(plat, need[: a.max_profiles], token, log, ov, a.show_input)
        json.dump(bios, open(P("raw/engager_profiles.json"), "w"), indent=1)
    elif os.path.exists(P("raw/engager_profiles.json")):
        bios = json.load(open(P("raw/engager_profiles.json")))

    # engagers = unique people who interacted, with whatever bio info we have
    eng = {}
    for c in comments:
        k = c["author"]
        e = eng.setdefault(k, {"author": k, "bio": c.get("author_bio") or "", "url": c.get("author_url"),
                               "comments": [], "reactions": 0, "posts_engaged": set()})
        e["comments"].append(c["text"][:300])
        e["posts_engaged"].add(c.get("post_url"))
        if c.get("author_followers") is not None:
            e["followers"] = c["author_followers"]
    for r in reactions:
        k = r["author"]
        e = eng.setdefault(k, {"author": k, "bio": r.get("author_bio") or "", "url": r.get("author_url"),
                               "comments": [], "reactions": 0, "posts_engaged": set()})
        e["reactions"] += 1
        e["posts_engaged"].add(r.get("post_url"))
    for k, b in bios.items():
        if k in eng:
            eng[k].update({kk: vv for kk, vv in b.items() if vv not in (None, "")})
    out = []
    for e in eng.values():
        e["posts_engaged"] = len([x for x in e["posts_engaged"] if x])
        out.append(e)
    json.dump(out, open(P("engagers.json"), "w"), indent=1, default=str)
    json.dump(log, open(logf, "w"), indent=1)
    print(json.dumps({"posts": len(posts), "comment_posts": len(chosen), "comments": len(comments),
                      "reactions": len(reactions), "engagers": len(out),
                      "engagers_with_bio": sum(1 for e in out if e.get("bio")),
                      "apify_usd": round(sum(x.get("usd", 0) for x in log), 3)}, indent=1))


if __name__ == "__main__":
    main()
