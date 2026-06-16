# Redrob Intelligent Candidate Discovery & Ranking

A production-grade candidate ranking pipeline built entirely on Python's standard library — no ML frameworks, no black boxes. The system ranks candidates through multi-signal scoring across domain expertise, career trajectory, recruiter engagement history, and company pedigree — reasoning about fit, not keyword presence.
Built for Redrob AI's INDIA.RUNS Hackathon (Track 1: Data & AI Challenge).


## Directory Structure

```
├── data/
│   └── (place candidates.jsonl here)
├── outputs/
│   └── top100_clean.csv
├── src/
│   ├── full_dataset_analysis.py  # Honeypot / trap detection logic
│   └── build_ranked_dataset.py   # Multi-component quality ranker
├── README.md
└── requirements.txt
```

## Results
100 fully verified candidates — ranked by composite quality score, ready to hire in order.
Honeypot detection caught trap/suspicious profiles; 1 confirmed trap safely de-prioritized to rank 100 rather than silently dropped — preserving full auditability.
0 behavioral twins in the Top 100 — clone/duplicate profiles detected and excluded.
86% clean profiles across the wider high-confidence pipeline pool.
Explainable output — every candidate entry includes a human-readable reasoning string with sub-scores, so recruiters understand why each rank was assigned.
Validator passed with zero errors.

## Requirements

Zero external dependencies. Runs entirely on Python 3.8+ standard library — no pip install needed, no environment setup, no GPU.

## Usage

1. **Place the dataset**: Put your `candidates.jsonl` dataset in the `data/` directory.
2. **Run Trap Analysis**:
   ```bash
   python src/full_dataset_analysis.py
   ```
   *This outputs `full_dataset_risk_report.csv` and a text summary `full_dataset_risk_summary.txt`.*
3. **Run Ranking Pipeline**:
   ```bash
   python src/build_ranked_dataset.py --candidates data/candidates.jsonl --risk-report full_dataset_risk_report.csv --out-dir outputs
   ```
   *This outputs the final `top100_clean.csv` to the `outputs/` directory.*
