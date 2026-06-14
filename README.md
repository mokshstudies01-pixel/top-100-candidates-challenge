# Redrob Intelligent Candidate Discovery & Ranking

This repository contains the reproduction code for generating the final `top100_clean.csv` submission file, containing 100% clean, verified candidates ranked by quality score.

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

## Requirements

No external dependencies are required. The pipeline runs entirely using Python's standard library.
Python 3.8+ is recommended.

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
