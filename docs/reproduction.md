# Reproduction Guide

This guide explains how to regenerate the paper-facing tables from the released
artifact data.

## Requirements

- Python 3.10 or newer
- No third-party Python packages are required

## Regenerate Tables

From the repository root:

```bash
python3 scripts/generate_paper_tables.py --check
```

Expected outputs:

```text
results/tables/main_metrics_and_union.csv
results/tables/category_metrics.csv
results/tables/chain_coverage.csv
results/tables/all_prompt_ablation.csv
results/tables/prompt_refinement.csv
results/tables/paper_tables.md
```

## Paper Table Mapping

- Paper Table I corresponds to `results/tables/main_metrics_and_union.csv`.
- Category-level details are in `results/tables/category_metrics.csv`.
- Chain-coverage details are in `results/tables/chain_coverage.csv`.
- The full e-series prompt-refinement results are in
  `results/tables/all_prompt_ablation.csv`.
- Paper Table II corresponds to `results/tables/prompt_refinement.csv`.

## Input Data Used by the Script

```text
data/actual_evaluation/e12_5runs/*/summary.json
data/prompt_ablation/experiments/*/summary.json
```

The script also reads coverage information embedded in the summary JSON files.

## Re-running LLM Calls

The Docker/DevContainer runtime can rerun `src/main.py`, but fresh LLM calls
require a valid API key for the selected provider. See
`docs/system_execution.md` for the runtime command. Table regeneration from the
released aggregate data does not require an API key.
