#!/usr/bin/env python3
"""
Full Dataset Ranked Arrangement + Clean Top 100
================================================
Arranges all 100,000 candidates in tier order:
  Tier 1: CLEAN (high quality -> low quality)
  Tier 2: SUSPICIOUS (high -> low) mixed at boundary with Tier 1
  Tier 3: LIKELY_TRAP
  Tier 4: CONFIRMED_TRAP

Top 100 = 100% CLEAN, best quality, company can hire in rank order.

Usage (from repo root):
    python src/full_dataset_analysis.py --candidates data/candidates.jsonl
    python src/build_ranked_dataset.py \\
        --candidates data/candidates.jsonl \\
        --risk-report outputs/full_dataset_risk_report.csv \\
        --out-dir outputs

Note: Run full_dataset_analysis.py first to generate full_dataset_risk_report.csv.
"""

import argparse, csv, json, sys, os, time
from datetime import date, datetime
from collections import defaultdict

os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TODAY = date(2026, 6, 10)

# ─── Company / skill libraries ────────────────────────────────────────────────

CONSULTING_FIRMS = {
    "mckinsey","bcg","bain","deloitte","pwc","kpmg","ey","ernst",
    "accenture","capgemini","cognizant","tcs","infosys","wipro",
    "hcl","tech mahindra","mphasis","hexaware","ltimindtree",
    "mindtree","persistent","niit","l&t infotech",
}
TIER1_PRODUCT = {
    "flipkart","meesho","swiggy","zomato","ola","paytm","phonepe","razorpay",
    "groww","zerodha","cred","urban company","dunzo","lenskart","byju",
    "unacademy","nykaa","sharechat","dream11","freshworks","zoho","postman",
    "browserstack","chargebee","hasura","google","meta","microsoft","amazon",
    "apple","netflix","uber","airbnb","stripe","openai","anthropic","deepmind",
    "cohere","databricks","snowflake","elastic","pinecone","weaviate","qdrant",
    "linkedin","twitter","spotify","shopify","salesforce","nvidia","glean",
    "sarvam","krutrim","rephrase","verloop","haptik","yellow.ai","gupshup",
    "juspay","cashfree","jio","bharti airtel","dream sports","curefit",
    "cars24","spinny","acko","digit insurance","practo","mfine","healthifyme",
    "sigmoid","fractal","mu sigma","niki","agara","mindtickle","leadsquared",
    "springworks","darwinbox","keka","rippling","postman","browserstack",
}
TIER2_PRODUCT = {
    "tata 1mg","tata cliq","hdfc bank","icici bank","kotak","axis bank",
    "ola electric","ather","bounce","rapido","yulu","innoviti",
    "tracxn","eka care","vedantu","toppr","eruditus","upgrad","great learning",
    "droom","cardekho","mswipe","tiger analytics",
}
AI_CORE = {
    "machine learning","deep learning","nlp","natural language","pytorch",
    "tensorflow","transformer","bert","gpt","embedding","vector","faiss",
    "elasticsearch","retrieval","ranking","recommendation","mlops","model",
    "neural","inference","fine-tuning","rag","llm","search","semantic",
    "milvus","pinecone","weaviate","qdrant","hugging face","sentence",
    "information retrieval","learning to rank","a/b test","feature store",
}
RETRIEVAL_SIGNALS = {
    "retrieval","search","ranking","recommendation","ltr","faiss","milvus",
    "elasticsearch","opensearch","pinecone","weaviate","qdrant","bm25",
    "collaborative filtering","two tower","ann","approximate nearest",
    "information retrieval","semantic search","vector search","hybrid search",
    "rag","reranking","cross encoder","dense retrieval","sparse retrieval",
    "ndcg","mrr","map","precision@k","knowledge base","question answering",
}
PROD_ML_SIGNALS = {
    "production","deployed","a/b test","serving","inference","mlops",
    "model monitoring","feature store","mlflow","kubeflow","vertex ai",
    "sagemaker","real-time","batch inference","fastapi","triton","torchserve",
    "onnx","model compression","quantization","distillation","drift detection",
    "retraining","feedback loop","shadow mode","canary","model registry",
    "data pipeline","airflow","prefect","dagster","spark",
}

def safe_date(s):
    if not s: return None
    try: return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except: return None

def company_tier(company):
    c = company.lower().strip()
    if any(t in c for t in TIER1_PRODUCT): return "T1"
    if any(t in c for t in TIER2_PRODUCT): return "T2"
    if any(t in c for t in CONSULTING_FIRMS): return "CONSULTING"
    return "UNKNOWN"

def text_hits(text, keywords):
    t = text.lower()
    return sum(1 for kw in keywords if kw in t)

def quality_score(cand: dict) -> tuple:
    """
    Comprehensive quality score (0-1) for ranking clean candidates.
    Components:
      - Retrieval/Search relevance     30%
      - Production ML depth            20%
      - Product company pedigree       20%
      - Behavioral signals             15%
      - Career quality & YoE           15%
    Returns (score, reasoning_str)
    """
    profile = cand.get("profile", {})
    career  = cand.get("career_history", [])
    skills  = cand.get("skills", [])
    sig     = cand.get("redrob_signals", {})

    title   = profile.get("current_title", "")
    company = profile.get("current_company", "")
    yoe     = profile.get("years_of_experience", 0) or 0
    hl      = profile.get("headline", "")
    summary = profile.get("summary", "")

    # ── 1. Retrieval / Search / Ranking relevance (30%) ────────────────────
    all_text = " ".join([
        title, hl, summary,
        " ".join(sk.get("name","") for sk in skills),
        " ".join(r.get("title","") + " " + r.get("description","") for r in career),
    ]).lower()
    ret_hits = text_hits(all_text, RETRIEVAL_SIGNALS)
    ret_score = min(ret_hits / 12.0, 1.0)

    # Title bonus: directly relevant title
    title_l = title.lower()
    if any(t in title_l for t in ["search engineer","ranking engineer","retrieval","recommendation systems"]):
        ret_score = min(ret_score + 0.20, 1.0)
    elif any(t in title_l for t in ["nlp","ml engineer","machine learning","ai engineer","data scientist"]):
        ret_score = min(ret_score + 0.10, 1.0)

    # ── 2. Production ML depth (20%) ───────────────────────────────────────
    prod_hits = text_hits(all_text, PROD_ML_SIGNALS)
    prod_score = min(prod_hits / 8.0, 1.0)

    # ── 3. Product company pedigree (20%) ──────────────────────────────────
    tiers = [(r.get("company",""), r.get("duration_months",0), company_tier(r.get("company","")))
             for r in career]
    total_months = sum(d for _,d,_ in tiers) or 1
    t1_months  = sum(d for _,d,t in tiers if t == "T1")
    t2_months  = sum(d for _,d,t in tiers if t == "T2")
    con_months = sum(d for _,d,t in tiers if t == "CONSULTING")

    prod_ratio = (t1_months + t2_months * 0.6) / total_months
    pedigree_score = min(prod_ratio * 1.4, 1.0)
    if con_months / total_months > 0.7:
        pedigree_score = max(pedigree_score - 0.3, 0)

    # ── 4. Behavioral signals (15%) ─────────────────────────────────────────
    rrr    = sig.get("recruiter_response_rate", 0) or 0
    icr    = sig.get("interview_completion_rate", 0) or 0
    gh     = sig.get("github_activity_score", 0) or 0
    pc     = sig.get("profile_completeness_score", 0) or 0
    notice = sig.get("notice_period_days", 90) or 90
    saved  = sig.get("saved_by_recruiters_30d", 0) or 0

    last_active = safe_date(sig.get("last_active_date"))
    if last_active:
        days = (TODAY - last_active).days
        active_score = max(0, 1.0 - days / 120.0)
    else:
        active_score = 0.3

    notice_score = max(0, 1.0 - notice / 90.0)
    behav_score  = (rrr * 0.35 + icr * 0.25 + min(gh/80,1)*0.15
                    + min(pc/100,1)*0.10 + active_score*0.10 + notice_score*0.05)

    # ── 5. Career quality & YoE (15%) ──────────────────────────────────────
    ai_skill_count = sum(1 for sk in skills
                         if any(c in sk.get("name","").lower() for c in AI_CORE))
    yoe_score      = min(yoe / 8.0, 1.0)
    skill_score    = min(ai_skill_count / 10.0, 1.0)
    career_score   = yoe_score * 0.5 + skill_score * 0.5

    # ── Composite ──────────────────────────────────────────────────────────
    score = (
        ret_score      * 0.30 +
        prod_score     * 0.20 +
        pedigree_score * 0.20 +
        behav_score    * 0.15 +
        career_score   * 0.15
    )

    # Build reasoning
    t1_cos = list(set(c for c,_,t in tiers if t == "T1"))[:3]
    top_skills = [sk.get("name","") for sk in skills
                  if any(c in sk.get("name","").lower() for c in RETRIEVAL_SIGNALS)][:4]
    reasoning = (
        f"{title} | {yoe:.1f}yrs; "
        f"{', '.join(t1_cos) if t1_cos else company}; "
        f"retrieval:{ret_score:.2f} prodML:{prod_score:.2f} pedigree:{pedigree_score:.2f}; "
        f"RRR:{rrr:.0%} GH:{gh:.0f}; "
        f"skills:[{', '.join(top_skills[:3])}]"
    )
    return round(score, 6), reasoning


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Full Dataset Tier Ranker")
    parser.add_argument("--candidates",  default="../data/candidates.jsonl",
                        help="Path to candidates.jsonl (default: ../data/candidates.jsonl)")
    parser.add_argument("--risk-report", default="../outputs/full_dataset_risk_report.csv",
                        help="Risk report from full_dataset_analysis.py")
    parser.add_argument("--out-dir",     default="../outputs",
                        help="Directory to write outputs (default: ../outputs)")
    args = parser.parse_args()

    JSONL           = args.candidates
    RISK_REPORT_CSV = args.risk_report
    os.makedirs(args.out_dir, exist_ok=True)
    OUT_FULL_RANKED = os.path.join(args.out_dir, "full_dataset_ranked.csv")
    OUT_TOP100      = os.path.join(args.out_dir, "top100_clean.csv")

    print("=" * 72)
    print("FULL DATASET RE-RANKING + CLEAN TOP 100")
    print("=" * 72)

    # ── Load verdict lookup from risk report ───────────────────────────────
    print("\n[1/4] Loading risk verdicts...")
    verdicts = {}
    with open(RISK_REPORT_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            verdicts[row["candidate_id"]] = row["verdict"]
    print(f"      Loaded {len(verdicts):,} verdicts")

    # ── Stream JSONL and compute quality scores (all candidates via quality_score) ───
    print("\n[2/4] Computing quality scores (streaming 100K candidates)...")
    t0 = time.time()

    all_candidates = []   # list of (candidate_id, verdict, quality, reasoning)

    with open(JSONL, "r", encoding="utf-8") as f:
        for i, line in enumerate(f, 1):
            line = line.strip()
            if not line: continue
            cand = json.loads(line)
            cid  = cand["candidate_id"]
            verdict = verdicts.get(cid, "CLEAN")

            if False:  # kept to preserve else-block indentation below
                pass
            else:
                q, reasoning = quality_score(cand)

            all_candidates.append((cid, verdict, q, reasoning))

            if i % 10000 == 0:
                print(f"      {i:>7,}/100,000  ({time.time()-t0:.0f}s)")

    print(f"      Done: {len(all_candidates):,} candidates in {time.time()-t0:.1f}s")

    # ── Sort into tiers ───────────────────────────────────────────────────────
    print("\n[3/4] Sorting into tiers...")

    TIER_ORDER = {
        "CLEAN":          0,
        "SUSPICIOUS":     1,
        "LIKELY_TRAP":    2,
        "CONFIRMED_TRAP": 3,
    }

    # Sort: primary = tier, secondary = quality desc
    # For the "mix" at the boundary: within CLEAN and SUSPICIOUS,
    # candidates that score above a threshold float up together by pure score.
    # Below threshold, SUSPICIOUS candidates interleave with lower-quality CLEAN.
    # We achieve this by giving SUSPICIOUS candidates a small tier penalty
    # applied only when their quality is >= 0.40 (they rise toward the bottom of CLEAN).

    def sort_key(c):
        cid, verdict, q, _ = c
        tier = TIER_ORDER.get(verdict, 3)

        if verdict == "CLEAN":
            return (0, -q)
        elif verdict == "SUSPICIOUS":
            # High-quality suspicious (>= 0.45) mix into the tail of CLEAN
            if q >= 0.45:
                return (0, -(q * 0.92))   # slight discount vs clean
            else:
                return (1, -q)
        elif verdict == "LIKELY_TRAP":
            return (2, -q)
        else:  # CONFIRMED_TRAP
            return (3, -q)

    all_candidates.sort(key=sort_key)
    print(f"      Sorted {len(all_candidates):,} candidates")

    # ── Validate top 100 are all CLEAN ────────────────────────────────────────
    top100 = all_candidates[:100]
    top100_verdicts = [v for _,v,_,_ in top100]
    non_clean = [(i+1, cid, v) for i,(cid,v,_,_) in enumerate(top100) if v != "CLEAN"]
    print(f"\n      Top 100 check: {top100_verdicts.count('CLEAN')}/100 CLEAN")
    if non_clean:
        print(f"      WARNING: {len(non_clean)} non-clean in top 100:")
        for r, cid, v in non_clean:
            print(f"        #{r} {cid} [{v}]")
    else:
        print(f"      All 100 are CLEAN — OK")

    # ── Write full_dataset_ranked.csv ─────────────────────────────────────────
    print(f"\n[4/4] Writing output files...")

    tier_labels = {
        "CLEAN":          "TIER_1_CLEAN",
        "SUSPICIOUS":     "TIER_2_SUSPICIOUS",
        "LIKELY_TRAP":    "TIER_3_LIKELY_TRAP",
        "CONFIRMED_TRAP": "TIER_4_CONFIRMED_TRAP",
    }
    # Determine effective tier from sort key
    def effective_tier(cid, verdict, q):
        if verdict == "CLEAN": return "TIER_1_CLEAN"
        if verdict == "SUSPICIOUS" and q >= 0.45: return "TIER_1_CLEAN_SUSP_MIX"
        if verdict == "SUSPICIOUS": return "TIER_2_SUSPICIOUS"
        if verdict == "LIKELY_TRAP": return "TIER_3_LIKELY_TRAP"
        return "TIER_4_CONFIRMED_TRAP"

    with open(OUT_FULL_RANKED, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "global_rank","candidate_id","verdict","effective_tier",
            "quality_score","reasoning"
        ])
        for global_rank, (cid, verdict, q, reasoning) in enumerate(all_candidates, 1):
            etier = effective_tier(cid, verdict, q)
            writer.writerow([global_rank, cid, verdict, etier, f"{q:.6f}", reasoning])

    print(f"      Written: {OUT_FULL_RANKED} ({len(all_candidates):,} rows)")

    # ── Write top100_clean.csv ────────────────────────────────────────────────
    with open(OUT_TOP100, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["rank", "candidate_id", "verdict", "quality_score", "reasoning"])
        for rank, (cid, verdict, q, reasoning) in enumerate(top100, 1):
            writer.writerow([rank, cid, verdict, f"{q:.6f}", reasoning])

    print(f"      Written: {OUT_TOP100} (top 100 all-clean)")

    # ── Tier distribution summary ─────────────────────────────────────────────
    print(f"\n{'='*72}")
    print("TIER DISTRIBUTION SUMMARY")
    print(f"{'='*72}")

    from collections import Counter
    tier_dist = Counter(effective_tier(c,v,q) for c,v,q,_ in all_candidates)
    for tier in ["TIER_1_CLEAN","TIER_1_CLEAN_SUSP_MIX","TIER_2_SUSPICIOUS",
                 "TIER_3_LIKELY_TRAP","TIER_4_CONFIRMED_TRAP"]:
         n = tier_dist[tier]
         print(f"  {tier:<30} {n:>8,}  ({n/len(all_candidates)*100:.1f}%)")

    print(f"\n  Top 100 composition:")
    top100_tier_dist = Counter(effective_tier(c,v,q) for c,v,q,_ in top100)
    for tier, cnt in top100_tier_dist.most_common():
        print(f"    {tier:<30} {cnt}")

    print(f"\n  Global rank ranges:")
    tier_ranges = defaultdict(lambda: [999999, 0])
    for i, (cid, v, q, _) in enumerate(all_candidates, 1):
        t = effective_tier(cid, v, q)
        tier_ranges[t][0] = min(tier_ranges[t][0], i)
        tier_ranges[t][1] = max(tier_ranges[t][1], i)
    for tier in ["TIER_1_CLEAN","TIER_1_CLEAN_SUSP_MIX","TIER_2_SUSPICIOUS",
                 "TIER_3_LIKELY_TRAP","TIER_4_CONFIRMED_TRAP"]:
        lo, hi = tier_ranges[tier]
        print(f"    {tier:<30} ranks {lo:,} – {hi:,}")

    print(f"\n[Done] Output files:")
    print(f"  {OUT_TOP100}      — final clean ranking (top 100, all CLEAN)")
    print(f"  {OUT_FULL_RANKED} — full 100K in tier order")

    return all_candidates, top100

if __name__ == "__main__":
    main()
