#!/usr/bin/env python3
"""
Convert browser-collected or user-uploaded data (CSV / XLSX / JSON) into the same
normalized files apify_fetch.py writes, so compute_metrics.py and verdict.py run unchanged.

Usage:
  python import_manual.py --platform linkedin --handle finnthormeier --followers 12400 \
      --bio "Headline / about text" --source "browser (Claude in Chrome) 2026-11-05" \
      --posts posts.csv [--engagers engagers.csv] [--audience audience.csv] --out runs/finnthormeier_linkedin

Column names are matched loosely (case/space-insensitive, common synonyms):
  posts:    url|link|post url, date|posted|published, format|type, views|impressions|plays,
            likes|reactions, comments, shares|reposts|retweets, saves|bookmarks, caption|text|title,
            duration_s|duration, sponsored, pinned, quotes
  engagers: post_url, name|username|author, headline_or_bio|headline|bio|title, action (comment|reaction),
            comment_text|comment|text, is_creator_reply
  audience: dimension, value, share_pct|percent|share

Dates may be ISO, "Nov 1, 2026", "01/11/2026" (day-first if --day-first), or relative like
"3d", "2w", "1mo", "5h" (resolved against --as-of, default now). Numbers may be "1,234" or "1.2K".
Empty cells stay empty: never fill them with guesses.
"""
import argparse, csv, json, os, re, sys
from datetime import datetime, timedelta, timezone

SYN = {
    "url": ["url", "link", "posturl", "postlink", "permalink", "videourl"],
    "date": ["date", "posted", "postedat", "published", "publishedat", "createdat", "time", "timestamp", "uploaddate"],
    "format": ["format", "type", "posttype", "mediatype", "contenttype"],
    "views": ["views", "impressions", "plays", "playcount", "viewcount", "reach"],
    "likes": ["likes", "reactions", "likecount", "reactioncount", "hearts", "diggcount"],
    "comments": ["comments", "commentcount", "replies", "replycount"],
    "shares": ["shares", "reposts", "retweets", "sharecount", "repostcount"],
    "saves": ["saves", "bookmarks", "collects", "savecount"],
    "quotes": ["quotes", "quotecount"],
    "caption": ["caption", "text", "title", "content", "description", "posttext"],
    "duration_s": ["durations", "duration", "length", "durationsec", "durationseconds"],
    "sponsored": ["sponsored", "ad", "isad", "paid", "partnership"],
    "pinned": ["pinned", "ispinned"],
    # engagers
    "post_url": ["posturl", "post", "url", "link"],
    "name": ["name", "username", "author", "handle", "user", "profile", "fullname"],
    "bio": ["headlineorbio", "headline", "bio", "title", "position", "description", "occupation"],
    "action": ["action", "type", "engagement", "kind"],
    "comment_text": ["commenttext", "comment", "text", "message"],
    "is_creator_reply": ["iscreatorreply", "creatorreply", "bycreator"],
    # audience
    "dimension": ["dimension", "category", "facet"],
    "value": ["value", "segment", "label", "name"],
    "share_pct": ["sharepct", "share", "percent", "percentage", "pct"],
}


def norm(h):
    return re.sub(r"[^a-z0-9]", "", (h or "").lower())


def read_rows(path, day_first=False):
    ext = os.path.splitext(path)[1].lower()
    if ext == ".json":
        d = json.load(open(path))
        return d if isinstance(d, list) else d.get("rows") or d.get("data") or []
    if ext in (".xlsx", ".xlsm"):
        try:
            import openpyxl
        except ImportError:
            sys.exit("openpyxl not installed: save the sheet as CSV or `pip install openpyxl`.")
        ws = openpyxl.load_workbook(path, read_only=True, data_only=True).worksheets[0]
        it = ws.iter_rows(values_only=True)
        hdr = [str(h or "") for h in next(it)]
        return [dict(zip(hdr, r)) for r in it if any(c not in (None, "") for c in r)]
    with open(path, newline="", encoding="utf-8-sig") as fh:
        sample = fh.read(4096)
        fh.seek(0)
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
        except csv.Error:
            dialect = csv.excel
        return [r for r in csv.DictReader(fh, dialect=dialect)]


def picker(rows, fields):
    hdr = {norm(h): h for h in (rows[0].keys() if rows else [])}
    m = {}
    for f in fields:
        for s in SYN[f]:
            if s in hdr and hdr[s] not in m.values():
                m[f] = hdr[s]
                break
    return m


def num(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    s = str(v).strip().replace(",", "").replace(" ", "").upper()
    m = re.match(r"^([\d.]+)([KMB])?\+?$", s)
    if not m:
        return None
    return float(m.group(1)) * {"K": 1e3, "M": 1e6, "B": 1e9}.get(m.group(2), 1)


def yes(v):
    return str(v or "").strip().lower() in ("1", "true", "yes", "y", "x", "sponsored", "ad", "paid")


def parse_date(v, as_of, day_first):
    if v in (None, ""):
        return None
    if isinstance(v, datetime):
        return (v if v.tzinfo else v.replace(tzinfo=timezone.utc)).isoformat()
    s = str(v).strip()
    m = re.match(r"^(\d+)\s*(m|min|h|hr|d|w|wk|mo|y|yr)s?\b", s.lower())
    if m:
        n, u = int(m.group(1)), m.group(2)
        delta = {"m": timedelta(minutes=n), "min": timedelta(minutes=n), "h": timedelta(hours=n), "hr": timedelta(hours=n),
                 "d": timedelta(days=n), "w": timedelta(weeks=n), "wk": timedelta(weeks=n),
                 "mo": timedelta(days=30 * n), "y": timedelta(days=365 * n), "yr": timedelta(days=365 * n)}[u]
        return (as_of - delta).isoformat()
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
        return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).isoformat()
    except ValueError:
        pass
    fmts = ["%b %d, %Y", "%B %d, %Y", "%d %b %Y", "%d %B %Y", "%Y/%m/%d"]
    fmts += ["%d/%m/%Y", "%d.%m.%Y"] if day_first else ["%m/%d/%Y", "%m/%d/%y"]
    for fmt in fmts:
        try:
            return datetime.strptime(s, fmt).replace(tzinfo=timezone.utc).isoformat()
        except ValueError:
            continue
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--platform", required=True, choices=["instagram", "tiktok", "youtube", "linkedin", "x"])
    ap.add_argument("--handle", required=True)
    ap.add_argument("--followers", type=float, required=True, help="follower/subscriber count as shown today")
    ap.add_argument("--bio", default="")
    ap.add_argument("--name", default=None)
    ap.add_argument("--business-account", action="store_true")
    ap.add_argument("--source", required=True, help='where the data came from + date, e.g. "browser 2026-11-05"')
    ap.add_argument("--posts", required=True)
    ap.add_argument("--engagers")
    ap.add_argument("--audience")
    ap.add_argument("--as-of", help="ISO datetime the data was collected (default now)")
    ap.add_argument("--day-first", action="store_true")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    as_of = datetime.fromisoformat(a.as_of).replace(tzinfo=timezone.utc) if a.as_of else datetime.now(timezone.utc)
    os.makedirs(a.out, exist_ok=True)
    P = lambda n: os.path.join(a.out, n)

    prows = read_rows(a.posts)
    pm = picker(prows, ["url", "date", "format", "views", "likes", "comments", "shares", "saves", "quotes",
                        "caption", "duration_s", "sponsored", "pinned"])
    missing = [f for f in ("date", "likes", "comments") if f not in pm]
    if missing:
        sys.exit(f"posts file is missing columns for: {missing}. Found headers: {list(prows[0].keys()) if prows else []}")
    posts, undated = [], 0
    for i, r in enumerate(prows):
        g = lambda f: r.get(pm[f]) if f in pm else None
        d = parse_date(g("date"), as_of, a.day_first)
        undated += d is None
        posts.append({"id": str(i), "url": g("url") or f"row-{i+1}", "date": d, "format": (g("format") or "").strip() or None,
                      "views": num(g("views")), "likes": num(g("likes")), "comments": num(g("comments")),
                      "shares": num(g("shares")), "saves": num(g("saves")), "quotes": num(g("quotes")),
                      "caption": str(g("caption") or ""), "duration_s": num(g("duration_s")),
                      "sponsored_flag": yes(g("sponsored")), "pinned": yes(g("pinned"))})
    prof = {"platform": a.platform, "handle": a.handle.lstrip("@"), "name": a.name, "followers": a.followers,
            "bio": a.bio, "is_business": a.business_account, "fetched_at": as_of.isoformat(), "data_source": a.source}
    json.dump(prof, open(P("profile.json"), "w"), indent=1)
    json.dump(posts, open(P("posts.json"), "w"), indent=1)

    comments, eng = [], {}
    if a.engagers:
        erows = read_rows(a.engagers)
        em = picker(erows, ["post_url", "name", "bio", "action", "comment_text", "is_creator_reply"])
        if "name" not in em:
            sys.exit(f"engagers file needs a name/username column. Found: {list(erows[0].keys()) if erows else []}")
        for r in erows:
            g = lambda f: r.get(em[f]) if f in em else None
            name = str(g("name") or "").strip()
            if not name:
                continue
            act = str(g("action") or ("comment" if g("comment_text") else "reaction")).lower()
            author = a.handle.lstrip("@") if yes(g("is_creator_reply")) else name
            e = eng.setdefault(author, {"author": author, "bio": "", "comments": [], "reactions": 0, "posts_engaged": set()})
            if g("bio"):
                e["bio"] = str(g("bio"))
            e["posts_engaged"].add(g("post_url"))
            if act.startswith("comment") or act.startswith("repl"):
                txt = str(g("comment_text") or "")
                comments.append({"post_url": g("post_url"), "author": author, "author_bio": e["bio"], "text": txt, "likes": None})
                e["comments"].append(txt[:300])
            else:
                e["reactions"] += 1
    out = []
    for k, e in eng.items():
        if k == a.handle.lstrip("@"):
            continue
        e["posts_engaged"] = len([x for x in e["posts_engaged"] if x])
        out.append(e)
    json.dump(comments, open(P("comments.json"), "w"), indent=1)
    json.dump(out, open(P("engagers.json"), "w"), indent=1)

    aud = []
    if a.audience:
        arows = read_rows(a.audience)
        am = picker(arows, ["dimension", "value", "share_pct"])
        for r in arows:
            g = lambda f: r.get(am[f]) if f in am else None
            aud.append({"dimension": g("dimension"), "value": g("value"), "share_pct": num(str(g("share_pct") or "").rstrip("%"))})
        json.dump(aud, open(P("audience.json"), "w"), indent=1)
    json.dump([{"actor": "manual import", "status": "SUCCEEDED", "source": a.source, "items": len(posts), "usd": 0}],
              open(P("fetch_log.json"), "w"), indent=1)
    print(json.dumps({"posts": len(posts), "undated_posts": undated, "columns_mapped": pm, "comments": len(comments),
                      "engagers": len(out), "audience_rows": len(aud), "source": a.source}, indent=1))
    if undated:
        print(f"[!] {undated} posts have no parseable date: fix them, or frequency/trend checks will be off.", file=sys.stderr)


if __name__ == "__main__":
    main()
