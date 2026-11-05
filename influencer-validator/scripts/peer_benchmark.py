#!/usr/bin/env python3
"""
Build a small peer reference for a creator who is NOT in the AI/marketing niche
(where the bundled research percentiles don't apply).

1. Pick 5-10 creators in the same niche, same platform, similar follower size (0.5x-2x).
2. For each: apify_fetch.py --url <link> --out runs/peers/<handle> --only posts   (posts only: cheap)
            compute_metrics.py --dir runs/peers/<handle>
3. python peer_benchmark.py --dirs runs/peers/* --group "TikTok fitness creators 10k-50k" --out runs/peers.json
4. Re-run compute_metrics.py on the target creator with --peers runs/peers.json

With so few peers the percentiles are rough; the report should say "vs N niche peers".
"""
import argparse, json, os


def pcts(vals):
    v = sorted(x for x in vals if x is not None)
    if len(v) < 3:
        return None
    def q(p):
        k = (len(v) - 1) * p / 100
        lo, hi = int(k), min(int(k) + 1, len(v) - 1)
        return round(v[lo] + (v[hi] - v[lo]) * (k - lo), 4)
    return {"n": len(v), "p10": q(10), "p25": q(25), "p50": q(50), "p75": q(75), "p90": q(90)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dirs", nargs="+", required=True)
    ap.add_argument("--group", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    ms = []
    for d in a.dirs:
        f = os.path.join(d, "metrics.json")
        if os.path.exists(f):
            ms.append(json.load(open(f)))
    out = {"group": f"{a.group} (n={len(ms)} peers)", "handles": [m.get("handle") for m in ms]}
    for k in ("median_er_pct", "median_views_to_followers", "er_by_views_pct", "avg_to_median_ratio", "posts_per_week"):
        out[k] = pcts([m.get(k) for m in ms])
    json.dump(out, open(a.out, "w"), indent=1)
    print(json.dumps(out, indent=1))


if __name__ == "__main__":
    main()
