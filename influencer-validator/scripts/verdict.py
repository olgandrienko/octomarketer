#!/usr/bin/env python3
"""
Combine hard metrics (metrics.json), the model's judgment labels (judgments.json)
and the campaign context (context.json) into a score, no-go gates and a verdict.
Writes verdict.json and report.md into --dir.

Usage:
  python verdict.py --dir ./runs/someuser_tiktok [--context ./runs/context.json]

context.json  (built from the project, or from what the user said; never ask for price)
{
  "product": "...", "icp": "...", "markets": "US, UK / English", "goal": "signups",
  "competitors": ["Brand A", "Brand B"], "near_competitors": ["..."],
  "source": "project: CLAUDE.md + /docs/positioning.md"  |  "user",
  "min_icp_share_pct": 15,                 # optional
  "price_quote_usd": null                  # only if the user volunteered it
}

judgments.json  (written by the model after reading to_classify.json; see references/judgment-rubric.md)
{
  "niche": "AI tools for marketers", "niche_matches_reference": true,   # AI/marketing research applies?
  "is_brand_account": false,
  "content_fit":  {"score": 0-5, "on_icp_topic_share_pct": 60, "evidence": "..."},
  "engager_labels": {"icp": 31, "adjacent": 22, "non_icp": 40, "bot_or_spam": 7, "unknown": 50,
                     "method": "linkedin headlines | ig bios | comment content only", "examples": ["..."]},
  "geo_language": {"score": 0-5 or null, "evidence": "most commenters write in Spanish; ICP is US"},
  "comment_labels": {"relevant_question": 12, "substantive": 30, "generic": 80, "cta_keyword": 0, "spam_bot": 9,
                     "examples": ["..."]},
  "use_case":     {"score": 0-5 or null, "evidence": "...", "best_example_url": "..."},
  "post_tags":    {"<post url>": "tutorial | news | opinion | listicle | case study | meme | ...", ...},
  "best_format_fit": {"score": 0-5, "evidence": "their best format is 15-min tutorials; product demo fits"},
  "brands": {"list": [{"name": "Notion", "posts": 2, "sponsored": true, "relation": "direct_competitor",
                       "last_date": "2026-10-01"}],
             "competitor_conflict": "none | near | direct_old | direct_recent", "evidence": "..."},
  "risks": ["optional: brand safety, undisclosed ads, controversy ..."]
}
"""
import argparse, json, math, os, statistics as st
from collections import defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
BENCH = json.load(open(os.path.join(HERE, "..", "data", "benchmarks.json")))

WEIGHTS = {  # 100 total, grouped
    # A. Real reach & consistency (35)
    "consistency": 10, "views_to_followers": 10, "engagement_level": 10, "habits_momentum": 5,
    # B. Audience fit (35)
    "icp_engagers": 20, "content_fit": 10, "geo_language": 5,
    # C. Audience quality (15)
    "relevant_questions": 10, "engagement_depth": 5,
    # D. Brand fit (15)
    "use_case": 8, "brand_situation": 4, "format_fit": 3,
}
GROUPS = [("A. Real reach & consistency", ["consistency", "views_to_followers", "engagement_level", "habits_momentum"]),
          ("B. Audience fit", ["icp_engagers", "content_fit", "geo_language"]),
          ("C. Audience quality", ["relevant_questions", "engagement_depth"]),
          ("D. Brand fit", ["use_case", "brand_situation", "format_fit"])]
LABELS = {"consistency": "Median vs average (no viral skew)", "views_to_followers": "Median views ÷ followers",
          "engagement_level": "Median engagement rate", "habits_momentum": "Posting frequency & trend",
          "icp_engagers": "Engagers who match the ICP", "content_fit": "Content ↔ ICP match",
          "geo_language": "Audience geography / language", "relevant_questions": "Relevant questions in comments",
          "engagement_depth": "Engagement depth & creator replies", "use_case": "Explains a product via real use case",
          "brand_situation": "Brands & competitors in content", "format_fit": "Product fits their best format"}


def clip(x, lo=0.0, hi=1.0):
    return max(lo, min(hi, x))


def from_pct(p):
    return None if p is None else clip((p - 10) / 65)


def avg(xs):
    xs = [x for x in xs if x is not None]
    return sum(xs) / len(xs) if xs else None


def gmean_rel(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None
    return round(2 ** st.mean(math.log2(max(v, 0) + 0.05) for v in vals), 2)


def f(x, suf=""):
    if x is None:
        return "n/a"
    if isinstance(x, bool):
        return "yes" if x else "no"
    if isinstance(x, int):
        return f"{x:,}{suf}"
    if isinstance(x, float):
        return f"{x:,.2f}{suf}" if abs(x) < 100 else f"{x:,.0f}{suf}"
    return f"{x}{suf}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", required=True)
    ap.add_argument("--context")
    a = ap.parse_args()
    P = lambda n: os.path.join(a.dir, n)
    m = json.load(open(P("metrics.json")))
    j = json.load(open(P("judgments.json")))
    cpath = a.context or (P("context.json") if os.path.exists(P("context.json")) else os.path.join(a.dir, "..", "context.json"))
    ctx = json.load(open(cpath)) if os.path.exists(cpath) else {}
    PN = m["platform"]
    min_icp = ctx.get("min_icp_share_pct", 15)
    pp = m.get("profile_position", {})
    nr = m.get("niche_reference", {})
    niche_ok = bool(j.get("niche_matches_reference")) or bool(nr.get("peer_file"))

    # ---------------- audience numbers
    el = j.get("engager_labels", {})
    known = sum(el.get(k, 0) for k in ("icp", "adjacent", "non_icp", "bot_or_spam"))
    icp_share = el.get("icp", 0) / known * 100 if known else None
    icp_adj = (el.get("icp", 0) + 0.5 * el.get("adjacent", 0)) / known * 100 if known else None
    bot_share = el.get("bot_or_spam", 0) / known * 100 if known else None
    cl = j.get("comment_labels", {})
    ctot = sum(v for v in cl.values() if isinstance(v, (int, float)))
    rq = cl.get("relevant_question", 0) / ctot * 100 if ctot else None
    subst = cl.get("substantive", 0) / ctot * 100 if ctot else None

    # ---------------- component scores (0..1, None = not checked)
    s = {}
    s["consistency"] = avg([pp.get("consistency_avg_to_median"), pp.get("best_post_share")])
    s["views_to_followers"] = None if PN == "LinkedIn" else (
        from_pct(nr.get("percentiles", {}).get("median_views_to_followers")) if niche_ok else pp.get("views_to_followers"))
    if niche_ok:
        s["engagement_level"] = from_pct(nr.get("percentiles", {}).get("median_er"))
        eng_basis = nr.get("group")
    else:
        g, b = BENCH["profiles"][PN]["good"]["median_er_pct"], BENCH["profiles"][PN]["bad"]["median_er_pct"]
        v = m.get("median_er_pct")
        s["engagement_level"] = None if not v else clip((math.log(v) - math.log(b)) / (math.log(g) - math.log(b)))
        eng_basis = f"{PN} good/bad profile anchors (other niche: rough guide)"
    fq = m.get("frequency", {})
    freq = None
    if fq:
        freq = 1.0 if fq.get("in_sweet_spot") else 0.15 if fq.get("above_danger_level") else 0.6
        if any(x["code"] == "frequency_dilution" for x in m["flags"]):
            freq -= 0.3
    tr = m.get("trend_last30_vs_before")
    trend = None if tr is None else clip((tr - 0.5) / 0.6)  # 0.5x -> 0, 1.1x+ -> 1
    s["habits_momentum"] = None if freq is None and trend is None else clip(avg([freq, trend]) if trend is not None and freq is not None
                                                                             else (freq if freq is not None else trend))
    s["icp_engagers"] = None if icp_adj is None else clip(icp_adj / 50)
    cf = j.get("content_fit", {}).get("score")
    s["content_fit"] = None if cf is None else clip(cf / 5)
    gl = (j.get("geo_language") or {}).get("score")
    s["geo_language"] = None if gl is None else clip(gl / 5)
    s["relevant_questions"] = None if rq is None else clip(rq / 15 * 0.7 + (subst or 0) / 40 * 0.3)
    replies = m.get("comments", {}).get("creator_replies", 0)
    depth_parts = [pp.get("comment_share_of_engagement")]
    if m.get("comments", {}).get("sampled"):
        depth_parts.append(1.0 if replies >= 5 else 0.6 if replies >= 1 else 0.2)
    if PN == "TikTok":
        mix = m.get("engagement_mix_pct", {})
        ss = (mix.get("shares") or 0) + (mix.get("saves") or 0)
        depth_parts.append(clip(ss / 35))  # good TikTok profiles: shares+saves ~35-40% of engagement
    s["engagement_depth"] = avg(depth_parts)
    uc = (j.get("use_case") or {}).get("score")
    s["use_case"] = None if uc is None else clip(uc / 5)
    br = j.get("brands") or {}
    conflict = br.get("competitor_conflict")
    bs = {"none": 1.0, "near": 0.7, "direct_old": 0.5, "direct_recent": 0.1}.get(conflict)
    dens = m.get("brands", {}).get("sponsored_share_pct")
    if bs is not None and dens is not None and dens >= 30:
        bs = min(bs, 0.4)
    s["brand_situation"] = bs
    ff = (j.get("best_format_fit") or {}).get("score")
    s["format_fit"] = None if ff is None else clip(ff / 5)

    w = dict(WEIGHTS)
    if s["views_to_followers"] is None and PN == "LinkedIn":
        w["consistency"] += w.pop("views_to_followers")
        s.pop("views_to_followers")
    have = {k: v for k, v in s.items() if v is not None}
    wsum = sum(w[k] for k in have)
    score = round(sum(have[k] * w[k] for k in have) / wsum * 100) if wsum else None
    missing = [k for k, v in s.items() if v is None]

    # ---------------- gates & conditions
    gates = [x for x in m["flags"] if x["level"] == "NO_GO"]
    if icp_share is not None and known >= 30 and icp_share < min_icp:
        gates.append({"level": "NO_GO", "code": "icp_mismatch",
                      "detail": f"Only {icp_share:.0f}% of classified engagers match the ICP (minimum {min_icp}%)."})
    if bot_share is not None and known >= 30 and bot_share >= 30:
        gates.append({"level": "NO_GO", "code": "bot_engagers_labeled", "detail": f"{bot_share:.0f}% of classified engagers are bots or spam."})
    if cf is not None and cf <= 1:
        gates.append({"level": "NO_GO", "code": "content_mismatch", "detail": "Content does not match the audience the campaign needs."})
    if j.get("is_brand_account"):
        gates.append({"level": "NO_GO", "code": "brand_account", "detail": "This is a brand/agency account, not an independent creator."})
    warns = [x for x in m["flags"] if x["level"] == "WARN"]
    conditions = []
    if conflict == "direct_recent":
        conditions.append("Promoted a direct competitor recently: confirm no exclusivity and expect a split audience reaction.")
    if gl is not None and gl <= 2:
        conditions.append("Audience geography/language doesn't match the target market well.")

    # ---------------- price (only if the user volunteered one)
    pc = {}
    price = ctx.get("price_quote_usd")
    mv, me = m.get("median_views"), m.get("median_engagement")
    icp_frac = icp_share / 100 if icp_share is not None else None
    if price:
        if mv:
            pc["cpm_usd"] = round(price / mv * 1000, 2)
            if icp_frac:
                pc["icp_cpm_usd"] = round(price / (mv * icp_frac) * 1000, 2)
        if me and icp_frac:
            pc["cost_per_icp_engagement_usd"] = round(price / (me * icp_frac), 2)

    # ---------------- verdict
    if gates:
        verdict = "NO-GO"
    elif score is None:
        verdict = "INSUFFICIENT DATA"
    elif score >= 70 and len(warns) <= 2 and not conditions:
        verdict = "GO"
    elif score >= 50:
        verdict = "CONDITIONAL"
    else:
        verdict = "NO-GO"
    confidence = "high"
    if m["sample_posts"] < 10 or known < 30 or len(missing) >= 3:
        confidence = "low"
    elif m["sample_posts"] < 15 or known < 60 or str(el.get("method", "")).startswith("comment content") or not niche_ok:
        confidence = "medium"

    # ---------------- content types (model tags -> performance)
    tags = j.get("post_tags") or {}
    tag_perf = []
    if tags:
        tc = json.load(open(P("to_classify.json")))
        rel = {p["url"]: p.get("rel_to_own_median") for p in tc.get("posts", [])}
        by = defaultdict(list)
        for url, t in tags.items():
            for tt in str(t).split("|"):
                if rel.get(url) is not None:
                    by[tt.strip()].append(rel[url])
        tag_perf = sorted([{"group": k, "n": len(v), "rel_to_own_median": gmean_rel(v)} for k, v in by.items()],
                          key=lambda x: -(x["rel_to_own_median"] or 0))

    out = {"verdict": verdict, "score": score, "confidence": confidence,
           "component_scores_0_1": {k: (round(v, 2) if v is not None else None) for k, v in s.items()},
           "weights_used": {k: w[k] for k in have}, "missing_components": missing, "engagement_basis": eng_basis,
           "gates": gates, "conditions": conditions, "warnings": warns, "price_check": pc,
           "icp": {"classified_engagers": known, "icp_share_pct": round(icp_share, 1) if icp_share is not None else None,
                   "icp_plus_half_adjacent_pct": round(icp_adj, 1) if icp_adj is not None else None,
                   "bot_share_pct": round(bot_share, 1) if bot_share is not None else None,
                   "icp_er_pct": round(m["median_er_pct"] * icp_frac, 4) if icp_frac is not None and m.get("median_er_pct") else None,
                   "icp_views_per_typical_post": round(mv * icp_frac) if mv and icp_frac is not None else None,
                   "method": el.get("method")},
           "comments": {"relevant_question_share_pct": round(rq, 1) if rq is not None else None,
                        "substantive_share_pct": round(subst, 1) if subst is not None else None, "classified": ctot},
           "content_type_performance": tag_perf}
    json.dump(out, open(P("verdict.json"), "w"), indent=1)

    # ---------------- report.md
    L = []
    L.append(f"# Influencer validation: {m.get('name') or ''} @{m['handle']} ({PN})\n")
    L.append(f"**Verdict: {verdict}** · score {f(score)}/100 · confidence {confidence}\n")
    L.append("<!-- SUMMARY: 3-5 plain sentences: verdict, the 1-2 numbers that decided it, next action -->\n")
    L.append(f"Validated against: **{ctx.get('product','?')}** → ICP: {ctx.get('icp','?')}"
             + (f" · markets: {ctx['markets']}" if ctx.get("markets") else "") + f" · source: {ctx.get('source','?')}\n")
    if gates:
        L.append("## No-go reasons\n")
        L += [f"- **{g['code']}**: {g['detail']}" for g in gates]
        L.append("")
    if conditions and not gates:
        L.append("## Conditions\n")
        L += [f"- {c}" for c in conditions]
        L.append("")
    L.append("## Scorecard\n")
    L.append("| Group | Criterion | Points |")
    L.append("|---|---|---|")
    for gname, keys in GROUPS:
        for k in keys:
            if k not in s:
                continue
            pts = "not checked" if s[k] is None else f"{s[k]*w[k]:.0f}/{w[k]}"
            L.append(f"| {gname} | {LABELS[k]} | {pts} |")
    L.append(f"\nEngagement level judged against: {eng_basis}.\n")

    L.append("## Real reach & consistency\n")
    good, bad = pp.get("good_profile_medians", {}), pp.get("bad_profile_medians", {})
    L.append(f"| Metric | This creator | Good-profile median | Bad-profile median |")
    L.append("|---|---|---|---|")
    L.append(f"| Avg ÷ median engagement (no-go ≥5x) | **{f(m.get('avg_to_median_ratio'),'x')}** | {f(good.get('avg_to_median'),'x')} | {f(bad.get('avg_to_median'),'x')} |")
    L.append(f"| Best post share of engagement (no-go ≥50%) | {f(m.get('best_post_share_pct'),'%')} | {f(good.get('best_post_share_pct'),'%')} | {f(bad.get('best_post_share_pct'),'%')} |")
    if PN != "LinkedIn":
        L.append(f"| Median views ÷ followers | {f(m.get('median_views_to_followers'))} | {f(good.get('median_views_to_followers'))} | {f(bad.get('median_views_to_followers'))} |")
    L.append(f"| Median ER | {f(m.get('median_er_pct'),'%')} | {f(good.get('median_er_pct'),'%')} | {f(bad.get('median_er_pct'),'%')} |")
    L.append(f"| Comments share of engagement | {f(m.get('engagement_mix_pct',{}).get('comments'),'%')} | {f(good.get('comments_share_of_engagement_pct'),'%')} | {f(bad.get('comments_share_of_engagement_pct'),'%')} |")
    L.append("")
    L.append(f"Followers {f(m.get('followers'))} · {m['sample_posts']} posts sampled · median engagement {f(m.get('median_engagement'))} vs average {f(m.get('avg_engagement'))} · median views {f(m.get('median_views'))} vs average {f(m.get('avg_views'))} · trend last 30 days {f(tr,'x')}\n")

    L.append("## Posting frequency vs engagement\n")
    if fq:
        sw = fq.get("sweet_spot_posts_per_week")
        band = fq.get("research_band") or {}
        L.append(f"- {f(m.get('posts_per_week'))} posts/week · {PN} sweet spot in the research: {sw[0]}–{sw[1]}/week "
                 f"({'inside' if fq.get('in_sweet_spot') else 'outside'}). Creators at this frequency had {f(band.get('rel_median_er'),'x')} "
                 f"peer engagement and {f(band.get('bad_pct'))}% were bad profiles.")
        L.append(f"- Busier weeks vs per-post engagement: rank correlation {f(fq.get('spearman_posts_in_week_vs_median_engagement'))} over {f(fq.get('weeks_observed'))} weeks "
                 "(negative = more posts dilute each post).")
        a6, b6 = fq.get("posts_within_6h_of_previous", {}), fq.get("posts_spaced_6h_plus", {})
        L.append(f"- Posts <6h after the previous one: {f(a6.get('rel_engagement'),'x')} typical (n={f(a6.get('n'))}); spaced posts: {f(b6.get('rel_engagement'),'x')} (n={f(b6.get('n'))}).")
    L.append("")

    L.append("## What content performs best for this creator\n")
    bd = m.get("content_breakdown", {})
    for dim, title in (("format", "Format"), ("duration", "Length"), ("caption_length", "Caption length"),
                       ("sponsored", "Sponsored vs organic"), ("hashtags", "Hashtags")):
        rows = [r for r in bd.get(dim, []) if r["n"] >= 2]
        if len(rows) >= 2 or (dim == "sponsored" and rows):
            L.append(f"- **{title}:** " + " · ".join(f"{r['group']} {f(r['rel_to_own_median'],'x')} (n={r['n']})" for r in rows))
    if tag_perf:
        L.append("- **Content type:** " + " · ".join(f"{r['group']} {f(r['rel_to_own_median'],'x')} (n={r['n']})" for r in tag_perf if r["n"] >= 2))
    L.append(f"- Best-format fit for the product: {f(ff)}/5. {(j.get('best_format_fit') or {}).get('evidence','')}")
    L.append("- Top posts: " + "; ".join(f"[{f(p['rel'],'x')}]({p['url']})" for p in m.get("top_posts", [])[:3]))
    L.append("")

    L.append("## Brands & competitors in their content\n")
    b = m.get("brands", {})
    L.append(f"- Brand deals in sample: {f(b.get('sponsored_posts'))} ({f(b.get('sponsored_share_pct'),'%')} of posts) · "
             f"their sponsored posts get {f(b.get('sponsored_rel_to_own_median'),'x')} typical engagement")
    for x in (br.get("list") or [])[:12]:
        L.append(f"- {x.get('name')}: {x.get('relation','?')}, {x.get('posts','?')} post(s)"
                 + (", sponsored" if x.get("sponsored") else "") + (f", last {x['last_date']}" if x.get("last_date") else ""))
    L.append(f"- Competitor conflict: **{conflict or 'not checked'}**. {br.get('evidence','')}")
    L.append("")

    L.append("## Audience\n")
    L.append(f"- ICP share of engagers: **{f(out['icp']['icp_share_pct'],'%')}** of {known} classified ({el.get('method','?')}) · "
             f"ICP + ½ adjacent {f(out['icp']['icp_plus_half_adjacent_pct'],'%')} · bots/spam {f(out['icp']['bot_share_pct'],'%')}")
    L.append(f"- ICP-weighted ER {f(out['icp']['icp_er_pct'],'%')} · ICP views per typical post ≈ {f(out['icp']['icp_views_per_typical_post'])}")
    if os.path.exists(P("audience.json")):
        aud = json.load(open(P("audience.json")))
        bydim = defaultdict(list)
        for r_ in aud:
            bydim[r_.get("dimension")].append(r_)
        for dim, rows_ in bydim.items():
            rows_.sort(key=lambda r_: -(r_.get("share_pct") or 0))
            L.append(f"- Audience {dim} (creator analytics): " + ", ".join(f"{r_['value']} {f(r_.get('share_pct'),'%')}" for r_ in rows_[:5]))
    L.append(f"- Geography/language: {f(gl)}/5. {(j.get('geo_language') or {}).get('evidence','')}")
    L.append(f"- Comments: relevant questions {f(rq,'%')}, substantive {f(subst,'%')} of {ctot} · creator replied {replies} times")
    if pc:
        L.append(f"- Quoted price → CPM {f(pc.get('cpm_usd'))} USD · ICP CPM {f(pc.get('icp_cpm_usd'))} USD · per ICP engagement {f(pc.get('cost_per_icp_engagement_usd'))} USD")
    L.append("")
    if warns:
        L.append("## Warnings\n")
        L += [f"- {x['code']}: {x['detail']}" for x in warns]
        L.append("")
    L.append("## Evidence\n")
    L.append(f"- Content fit ({f(cf)}/5): {(j.get('content_fit') or {}).get('evidence','')}")
    L.append(f"- Use case ({f(uc)}/5): {(j.get('use_case') or {}).get('evidence','')} {(j.get('use_case') or {}).get('best_example_url','')}")
    for ex in (el.get("examples") or [])[:5]:
        L.append(f"- Engager: {ex}")
    for ex in (cl.get("examples") or [])[:5]:
        L.append(f"- Comment: {ex}")
    for r in j.get("risks") or []:
        L.append(f"- Risk: {r}")
    L.append("")
    L.append("## Data & confidence\n")
    L.append(f"- Data source: **{m.get('data_source','?')}**, collected {str(m.get('collected_at') or '?')[:16].replace('T',' ')} UTC. Fresh data only; no older snapshots used.")
    L.append(f"- Sample: {m['sample_posts']} posts (excluded: {m.get('excluded')}), {m.get('comments',{}).get('sampled',0)} comments, {m.get('engagers',{}).get('total',0)} engagers. Not checked: {', '.join(LABELS[k] for k in missing) or 'nothing'}.")
    L.append(f"- Niche: {j.get('niche','?')} · research percentiles {'used' if niche_ok else 'not used (different niche); judged against good/bad profile patterns'}.")
    L.append("")
    open(P("report.md"), "w").write("\n".join(L))
    print(json.dumps({k: out[k] for k in ("verdict", "score", "confidence")}, indent=1))
    for g in gates:
        print("[NO_GO]", g["detail"])
    for c in conditions:
        print("[CONDITION]", c)


if __name__ == "__main__":
    main()
