# Reproduction Guide

This guide explains how to rebuild the short-paper result tables from the
released artifact data.

Here, "regenerate tables" means: read the released summary JSON files under
`data/`, compute the table rows again, and write fresh CSV/Markdown files under
`results/tables/`. This is a data-consistency check. It does not rerun the LLM
pipeline, does not contact any LLM API, and does not require Docker.

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

The command is deterministic over the released `data/` files. It does not call
an LLM API and does not require Docker.

Inputs:

```text
data/actual_evaluation/e12_5runs/*/summary.json
data/prompt_ablation/experiments/*/summary.json
```

Outputs:

```text
results/tables/
```

## Paper Table Mapping

- Paper Table I corresponds to `results/tables/main_metrics_and_union.csv`.
- Category-level details are in `results/tables/category_metrics.csv`.
- Chain-coverage details are in `results/tables/chain_coverage.csv`.
- The full e-series prompt-refinement results are in
  `results/tables/all_prompt_ablation.csv`.
- Paper Table II corresponds to `results/tables/prompt_refinement.csv`.

## Inspect Released Data

Quick checks:

```bash
head -n 5 bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv
head -n 5 results/tables/main_metrics_and_union.csv
sqlite3 data/derived_databases/consensus_results_e12_5runs.db '.tables'
sqlite3 data/derived_databases/chain_coverage_e12_5runs.db '.tables'
```

Useful SQLite queries:

```sql
select model_name, count(*) as rows
from consensus_votes
group by model_name
order by model_name;

select model_id, count(*) as runs, avg(coverage_percent) as avg_coverage
from coverage_per_run
group by model_id
order by model_id;
```

These databases are inspection snapshots. The authoritative paper tables are
generated from the JSON summaries under `data/`.

## Re-running LLM Calls

The Docker/DevContainer runtime can rerun `src/main.py`, but fresh LLM calls
require a valid API key for the selected provider. See
`system_execution.md` for the runtime command. Table regeneration from the
released aggregate data does not require an API key.
