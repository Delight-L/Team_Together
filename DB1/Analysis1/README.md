# Analysis 1 Agent-ready module

This package implements the approved DB1 Analysis 1 statistical core as a reusable Python module.

## Important boundary
`analysis/analysis1.py` starts from a **one-row-per-dong preprocessed table**. Source-specific SKT grid spatial joins, Seoul/public API schemas, and quarterly reshaping are intentionally not guessed here. They should be implemented as source adapters once the live API schemas are fixed.

The statistical core follows:
1. validate 22 dongs
2. PCA for active-population, time-structure, resident-age and household-structure blocks
3. build 13 features
4. Z-score + 1/sqrt(n) domain balancing
5. K-Means k=2..6 diagnostics
6. perturbation ARI
7. final k=3
8. reconnect labels to original-variable profile
9. save machine-readable outputs and run manifest

## VSCode
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt

python run_analysis1.py \
  --input data/processed/analysis1_input.csv \
  --mapping pca_columns.json \
  --profile data/processed/analysis1_profile.csv \
  --period 2025H2 \
  --version 2025-12 \
  --output data/results/analysis1/2025-12
```

Copy `pca_columns.example.json` to `pca_columns.json` and replace placeholders with the actual processed-column names.

## Future Agent
The future orchestrator should call `run_analysis1()` and inspect:
`status`, `validation`, `metrics`, `warnings`, `outputs`, and `requires_human_review`.
The Agent should not autonomously rewrite the statistical methodology.
