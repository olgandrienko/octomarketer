#!/usr/bin/env python3
"""
Rank several validated accounts (several creators, or one creator on several platforms)
and detect cross-posting between accounts of the same person.

Usage:
  python compare.py --dirs runs/a_tiktok runs/a_instagram runs/b_youtube --out runs/comparison.md
  Accounts of the same person: pass --person "Name=runs/a_tiktok,runs/a_instagram" (repeatable)

Each dir needs metrics.json and verdict.json (run compute_metrics.py + verdict.py first).
Cross-post rule from the research: posts on two platforms <=7 days apart with caption overlap
(Jaccard >= 0.5, or 70% of the shorter caption's words in the other) count as the same post.
"""
import argparse, json, os, re
from datetime import datetime


def words(t):
    return set(re.findall(r"[a-z0-9']{3,}", (t or "").lower()))


def dt(s):
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00")).replace(tzinfo=None)
    except Exception:
        return None


def crosspost(d1, d2):
    p1 = json.load(open(os.path.join(d1, "posts.json")))
    p2 = json.load(open(os.path.join(d2, "posts.json")))
    matched = 0
    comparable = 0
    for a in p1:
        wa, ta = words(a.get("caption")), dt(a.get("date"))
        if len(wa) < 6 or not ta:
            continue
        comparable += 1
        for b in p2:
            wb, tb = words(b.get("caption")), dt(b.get("date"))
            if len(wb) < 6 or not tb or abs((ta - tb).days) > 7:
                continue
            inter = len(wa & wb)
            if inter / len(wa | wb) >= 0.5 or inter / min(len(wa), len(wb)) >= 0.7:
                matched += 1
                break
    return matched, comparable


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--person", action="append", default=[])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    rows = []
    for d in a.dirs:
        m = json.load(open(os.path.join(d, "metrics.json")))
        v = json.load(open(os.path.join(d, "verdict.json")))
        rows.append((d, m, v))
    order = {"GO": 0, "CONDITIONAL": 1, "INSUFFICIENT DATA": 2, "NO-GO": 3}
    rows.sort(key=lambda r: (order.get(r[2]["verdict"], 9), -(r[2]["score"] or 0)))
    L = ["# Creator comparison\n",
         "| # | Account | Platform | Followers | Median ER | Avg÷median | Median views÷followers | Posts/wk | ICP share | Sponsored % | Score | Verdict |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for i, (d, m, v) in enumerate(rows, 1):
        L.append(f"| {i} | @{m['handle']} | {m['platform']} | {m.get('followers') or 'n/a'} | {m.get('median_er_pct')}% | "
                 f"{m.get('avg_to_median_ratio')}x | {m.get('median_views_to_followers', 'n/a')} | {m.get('posts_per_week')} | "
                 f"{v['icp'].get('icp_share_pct')}% | {m.get('brands', {}).get('sponsored_share_pct')}% | {v['score']} | **{v['verdict']}** |")
    for spec in a.person:
        name, ds = spec.split("=", 1)
        ds = [x.strip() for x in ds.split(",") if x.strip()]
        L.append(f"\n## {name}: which platform to buy\n")
        best = sorted([r for r in rows if r[0] in ds], key=lambda r: -(r[2]["score"] or 0))
        if best:
            L.append(f"Strongest account: @{best[0][1]['handle']} on {best[0][1]['platform']} (score {best[0][2]['score']}, "
                     f"{best[0][2]['verdict']}). Judge each platform on its own median, not on the person's best platform.")
        for i in range(len(ds)):
            for k in range(i + 1, len(ds)):
                mt, cp = crosspost(ds[i], ds[k])
                share = round(mt / cp * 100) if cp else 0
                tag = "clearly cross-posts" if share >= 25 and mt >= 3 else "some overlap" if mt else "no overlap"
                L.append(f"- {os.path.basename(ds[i])} ↔ {os.path.basename(ds[k])}: {mt}/{cp} posts match ({share}%): {tag}")
        L.append("\nCross-posting means the same people may see the post twice: buying both platforms adds less reach than the follower counts suggest.")
    open(a.out, "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
