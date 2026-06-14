#!/usr/bin/env python3
"""
Full-Dataset Trap Analysis
==========================
Runs the same detect_trap() logic used on submission_v3 across
all 100,000 candidates and produces a complete breakdown.
"""

import csv, json, sys, os, time
from datetime import date, datetime
from collections import Counter, defaultdict

os.environ["PYTHONIOENCODING"] = "utf-8"
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

TODAY = date(2026, 6, 10)
JSONL = "[PUB] India_runs_data_and_ai_challenge\\[PUB] India_runs_data_and_ai_challenge\\India_runs_data_and_ai_challenge\\candidates.jsonl"
OUT_SUMMARY = "full_dataset_risk_summary.txt"
OUT_CSV     = "full_dataset_risk_report.csv"

# ─── Same company / skill libraries as trap_audit_v3.py ───────────────────────

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
    "linkedin","twitter","spotify","shopify","salesforce","nvidia",
    "sarvam","krutrim","glean","vectara","rephrase",
}
WEAK_TITLES = {
    "hr manager","human resources","accountant","marketing manager",
    "content writer","graphic designer","operations manager","sales executive",
    "customer support","project manager","mechanical engineer","civil engineer",
    "business analyst","financial analyst","recruiter","administrative",
    "digital marketing","seo specialist","social media",
}
AI_CORE = {
    "machine learning","deep learning","nlp","natural language","pytorch",
    "tensorflow","transformer","bert","gpt","embedding","vector","faiss",
    "elasticsearch","retrieval","ranking","recommendation","mlops","model",
    "neural","inference","fine-tuning","rag","llm","search","semantic",
}

def safe_date(s):
    if not s: return None
    try: return datetime.strptime(str(s)[:10], "%Y-%m-%d").date()
    except: return None

def company_tier(company):
    c = company.lower().strip()
    if any(t in c for t in TIER1_PRODUCT): return "T1"
    if any(t in c for t in CONSULTING_FIRMS): return "CONSULTING"
    return "UNKNOWN"

# ─── detect_trap() — identical logic to trap_audit_v3.py ─────────────────────

def detect_trap(cand):
    profile = cand.get("profile", {})
    career  = cand.get("career_history", [])
    skills  = cand.get("skills", [])
    edu     = cand.get("education", [])
    sig     = cand.get("redrob_signals", {})
    flags   = []
    score   = 0.0
    trap_types = []

    title   = profile.get("current_title", "")
    yoe     = profile.get("years_of_experience", 0)

    # A: Impossible Timeline
    for edu_item in edu:
        end_yr = edu_item.get("end_year", 9999)
        if not end_yr or end_yr > 2030: continue
        for role in career:
            rs = safe_date(role.get("start_date", ""))
            if rs and rs.year < end_yr - 1:
                flags.append("IMPOSSIBLE_TIMELINE")
                score += 0.50
    if "IMPOSSIBLE_TIMELINE" in flags:
        trap_types.append("IMPOSSIBLE_TIMELINE")

    # B: Skill Duration Mismatch
    sdm = 0
    for sk in skills:
        if sk.get("proficiency") in ("expert","advanced") and sk.get("duration_months",99) <= 2:
            sdm += 1
            score += 0.15
    if sdm: trap_types.append("SKILL_DURATION_MISMATCH")

    # C: Skill Explosion
    if len(skills) > 18:
        adv = sum(1 for sk in skills if sk.get("proficiency") in ("expert","advanced"))
        if adv / len(skills) > 0.85:
            flags.append("KEYWORD_STUFFER")
            score += 0.35
            trap_types.append("KEYWORD_STUFFER")

    # D: Title / Skill Mismatch
    if any(w in title.lower() for w in WEAK_TITLES):
        ai_skills = [sk for sk in skills if any(c in sk.get("name","").lower() for c in AI_CORE)]
        if len(ai_skills) >= 5:
            flags.append("TITLE_MISMATCH")
            score += 0.60
            trap_types.append("TITLE_MISMATCH")

    # E: Behavioral Anomalies
    rrr  = sig.get("recruiter_response_rate", -1)
    icr  = sig.get("interview_completion_rate", -1)
    oar  = sig.get("offer_acceptance_rate", -1)
    pc   = sig.get("profile_completeness_score", -1)
    gh   = sig.get("github_activity_score", -1)
    saved= sig.get("saved_by_recruiters_30d", 0)

    near_perfect = sum([rrr >= 0.99, icr >= 0.99, oar >= 0.99, pc >= 99, gh >= 98])
    if near_perfect >= 4:
        flags.append("HONEYPOT_SIGNALS")
        score += 0.65
        trap_types.append("HONEYPOT_SIGNALS")

    if icr >= 0.95 and rrr <= 0.05:
        flags.append("SIGNAL_CONTRADICTION")
        score += 0.80
        trap_types.append("SIGNAL_CONTRADICTION")

    if rrr == 1.0 and icr == 1.0 and oar == 1.0:
        flags.append("SYNTHETIC_PROFILE")
        score += 0.90
        trap_types.append("SYNTHETIC_PROFILE")

    if saved >= 50 and gh == 0 and rrr >= 0.90:
        flags.append("INFLATED_SIGNALS")
        score += 0.30
        trap_types.append("INFLATED_SIGNALS")

    notice = sig.get("notice_period_days", 90)
    if notice == 0 and rrr >= 0.98 and icr >= 0.98:
        flags.append("HONEYPOT_NOTICE")
        score += 0.40
        trap_types.append("HONEYPOT_NOTICE")

    # F: Career Description Mismatch
    NON_AI = ["invoice","ledger","seo strategy","brand identity","social media campaign",
              "tax filing","recruitment drive","purchase orders","payroll","audit report",
              "cold calling","lead generation","content calendar","brand awareness"]
    for role in career[:3]:
        rt    = role.get("title","").lower()
        rdesc = role.get("description","").lower()
        if any(a in rt for a in ["engineer","scientist","analyst","ml","ai","nlp"]):
            hits = [kw for kw in NON_AI if kw in rdesc]
            if hits:
                flags.append("DESC_MISMATCH")
                score += 0.35
                trap_types.append("DESC_MISMATCH")
                break

    # G: All-Consulting Career
    if career:
        cons = sum(1 for r in career if company_tier(r.get("company","")) == "CONSULTING")
        if cons == len(career) and len(career) >= 2:
            flags.append("ALL_CONSULTING")
            score += 0.30
            trap_types.append("ALL_CONSULTING")

    # H: YoE Inflation
    if career and yoe > 0:
        total_mo = sum(r.get("duration_months",0) for r in career)
        actual   = total_mo / 12
        if yoe > actual + 6:
            flags.append("YOE_INFLATION")
            score += 0.20
            trap_types.append("YOE_INFLATION")
        if total_mo == 0:
            flags.append("EMPTY_CAREER")
            score += 0.50
            trap_types.append("EMPTY_CAREER")

    # I: Stagnation
    if "junior" in title.lower() and yoe >= 5:
        flags.append("STAGNATION")
        score += 0.15
        trap_types.append("STAGNATION")

    # J: No GitHub with heavy AI claims
    ai_skill_count = sum(1 for sk in skills if any(c in sk.get("name","").lower() for c in AI_CORE))
    if gh == 0 and ai_skill_count >= 8:
        flags.append("NO_GITHUB")
        score += 0.15
        trap_types.append("NO_GITHUB")

    # K: Profile Completeness Anomaly
    if pc < 50 and saved >= 30:
        flags.append("PC_ANOMALY")
        score += 0.20
        trap_types.append("PC_ANOMALY")

    score = min(score, 1.0)
    if score >= 0.65:   verdict = "CONFIRMED_TRAP"
    elif score >= 0.40: verdict = "LIKELY_TRAP"
    elif score >= 0.20: verdict = "SUSPICIOUS"
    else:               verdict = "CLEAN"

    return verdict, round(score, 3), list(set(trap_types))


# ─── Main ─────────────────────────────────────────────────────────────────────

def main():
    print("=" * 70)
    print("FULL DATASET TRAP ANALYSIS — 100,000 CANDIDATES")
    print("=" * 70)
    print(f"[Start] Streaming {JSONL}...")
    t0 = time.time()

    # Counters
    verdict_counts   = Counter()
    trap_type_counts = Counter()
    industry_traps   = defaultdict(lambda: Counter())
    score_buckets    = Counter()   # 0-0.1, 0.1-0.2, ... 0.9-1.0
    per_flag_count   = Counter()

    total = 0
    csv_rows = []   # store per-candidate summary for CSV output

    with open(JSONL, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            cand = json.loads(line)
            total += 1

            verdict, conf, trap_types = detect_trap(cand)
            verdict_counts[verdict] += 1

            # Bucket score
            bucket = f"{int(conf*10)*0.1:.1f}-{int(conf*10)*0.1+0.1:.1f}"
            score_buckets[bucket] += 1

            # Trap type breakdown
            for tt in trap_types:
                trap_type_counts[tt] += 1
                per_flag_count[tt] += 1

            # Industry breakdown
            profile = cand.get("profile", {})
            industry = profile.get("current_industry", "Unknown") or "Unknown"
            industry_traps[industry][verdict] += 1

            # CSV row
            sig = cand.get("redrob_signals", {})
            csv_rows.append({
                "candidate_id": cand["candidate_id"],
                "verdict": verdict,
                "confidence": conf,
                "trap_types": "|".join(trap_types) if trap_types else "",
                "current_title": profile.get("current_title",""),
                "current_company": profile.get("current_company",""),
                "industry": industry,
                "yoe": profile.get("years_of_experience",0),
                "rrr": sig.get("recruiter_response_rate",""),
                "icr": sig.get("interview_completion_rate",""),
                "github": sig.get("github_activity_score",""),
            })

            if total % 10000 == 0:
                elapsed = time.time() - t0
                print(f"  Progress: {total:>7,}/100,000  ({elapsed:.0f}s)")

    elapsed = time.time() - t0
    print(f"  Done: {total:,} candidates in {elapsed:.1f}s\n")

    # ── Write CSV ──────────────────────────────────────────────────────────────
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(csv_rows[0].keys()))
        writer.writeheader()
        writer.writerows(csv_rows)
    print(f"[Output] {OUT_CSV} written ({len(csv_rows):,} rows)")

    # ── Build text summary ─────────────────────────────────────────────────────
    lines = []
    SEP  = "=" * 70
    sep  = "-" * 70

    lines.append(SEP)
    lines.append("FULL DATASET TRAP ANALYSIS — SUMMARY REPORT")
    lines.append(f"Dataset: 100,000 candidates | Analysed: {total:,}")
    lines.append(SEP)

    lines.append("")
    lines.append("VERDICT BREAKDOWN")
    lines.append(sep)
    for v in ["CLEAN","SUSPICIOUS","LIKELY_TRAP","CONFIRMED_TRAP"]:
        n = verdict_counts[v]
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        lines.append(f"  {v:<20} {n:>7,}  ({pct:5.1f}%)  {bar}")

    lines.append("")
    lines.append("TRAP CATEGORY SUMMARY")
    lines.append(sep)
    trap_total = verdict_counts["CONFIRMED_TRAP"] + verdict_counts["LIKELY_TRAP"]
    susp_total = verdict_counts["SUSPICIOUS"]
    clean_total= verdict_counts["CLEAN"]
    lines.append(f"  Traps (Confirmed + Likely): {trap_total:>7,}  ({trap_total/total*100:.1f}%)")
    lines.append(f"  Suspicious (borderline):    {susp_total:>7,}  ({susp_total/total*100:.1f}%)")
    lines.append(f"  Clean:                      {clean_total:>7,}  ({clean_total/total*100:.1f}%)")
    lines.append(f"  'Correct' candidates*:      {clean_total+susp_total:>7,}  ({(clean_total+susp_total)/total*100:.1f}%)")
    lines.append(f"  * Clean + Suspicious (borderline, not definitively traps)")

    lines.append("")
    lines.append("TRAP TYPE FREQUENCY (multi-label, sorted by count)")
    lines.append(sep)
    for tt, cnt in trap_type_counts.most_common():
        pct = cnt / total * 100
        lines.append(f"  {tt:<30} {cnt:>7,}  ({pct:5.1f}%)")

    lines.append("")
    lines.append("CONFIDENCE SCORE DISTRIBUTION")
    lines.append(sep)
    for bucket in sorted(score_buckets.keys()):
        n   = score_buckets[bucket]
        pct = n / total * 100
        bar = "#" * int(pct / 2)
        lines.append(f"  conf {bucket}  {n:>7,}  ({pct:5.1f}%)  {bar}")

    lines.append("")
    lines.append("TOP 15 INDUSTRIES BY TRAP RATE")
    lines.append(sep)
    industry_trap_rates = []
    for ind, vcounts in industry_traps.items():
        ind_total = sum(vcounts.values())
        ind_traps = vcounts["CONFIRMED_TRAP"] + vcounts["LIKELY_TRAP"]
        if ind_total >= 50:   # only industries with enough data
            industry_trap_rates.append((ind, ind_total, ind_traps, ind_traps/ind_total))
    industry_trap_rates.sort(key=lambda x: -x[3])
    for ind, ind_total, ind_traps, rate in industry_trap_rates[:15]:
        lines.append(f"  {ind[:35]:<36} {ind_traps:>5,}/{ind_total:<6,} ({rate*100:5.1f}%)")

    lines.append("")
    lines.append("BOTTOM 10 INDUSTRIES (cleanest)")
    lines.append(sep)
    for ind, ind_total, ind_traps, rate in industry_trap_rates[-10:]:
        lines.append(f"  {ind[:35]:<36} {ind_traps:>5,}/{ind_total:<6,} ({rate*100:5.1f}%)")

    lines.append("")
    lines.append(SEP)
    lines.append("KEY INSIGHT")
    lines.append(SEP)
    lines.append(f"  {trap_total/total*100:.1f}% of the dataset ({trap_total:,} candidates)")
    lines.append(f"  are confirmed or likely challenge traps.")
    lines.append(f"  The dataset is {clean_total/total*100:.1f}% genuinely clean candidates.")
    lines.append("")

    # Print and save
    report = "\n".join(lines)
    print(report)

    with open(OUT_SUMMARY, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"\n[Output] {OUT_SUMMARY} written")

if __name__ == "__main__":
    main()
