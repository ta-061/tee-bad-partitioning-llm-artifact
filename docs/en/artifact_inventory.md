# Artifact Inventory

This document explains what is included in the public artifact and how to
interpret each group of files. The repository includes both data used to rebuild
the short-paper tables and supplemental data collected during the study.

## Data Tiers

Paper-table data is the authoritative input used to regenerate the short-paper
tables. It is documented by the reproduction guide and consumed by
`scripts/generate_paper_tables.py` or the evaluation scripts.

Supplemental data contains collected outputs that are useful for
transparency, future full-paper analysis, or independent inspection, but are not
all described in the short paper. Supplemental data must preserve enough
provenance to be understandable, but readers should not infer that every
supplemental file supports a reported short-paper table.

## Kept

Runtime and benchmark:

- `src/`: TEE Flow Inspector implementation used for the LLM pipeline
- `prompts/`: e-series prompt versions, including the final e12 setting
- `benchmark/partitioningE/bad-partitioning/`: compact runtime-compatible TA
  benchmark path
- `.devcontainer/` and `docker/`: reproducible container environment
- `src/llm_settings/llm_config.example.json`: safe configuration template

Ground truth and baselines:

- `bad-partitioning-ta_groundtruth_labels/category_labels/`
- `bad-partitioning-ta_groundtruth_labels/flow_labels/ta_candidate_flows.json`
- `benchmark/partitioningE_bad_partitioning/labels/`
- `benchmark/partitioningE_bad_partitioning/diting/`
- `src/metrics/DITING_ans.csv`

Paper-table aggregate data:

- `data/actual_evaluation/e12_5runs/`: five-run consensus metrics for nine
  models
- `data/prompt_ablation/experiments/`: e-series prompt-ablation summaries
- `results/tables/`: regenerated CSV/Markdown tables used by the paper
- `results/source_tables/`: reference Markdown table copies for inspection
- `results/source_tables/original_aggregation_workspace/`: fuller copied
  Markdown table snapshots from the original aggregation workspace, with local
  paths and private note metadata removed or replaced

Supplemental data:

- `data/prompt_ablation/raw_runs/`: archived one-run detector outputs retained
  for future full-paper analysis and provenance checks

Inspection databases:

- `data/derived_databases/consensus_results_e12_5runs.db`
- `data/derived_databases/chain_coverage_e12_5runs.db`

The database files are included because they are compact enough and make it
easy to inspect consensus votes, DITING overlap, and chain-coverage rows without
rerunning the aggregation scripts.

## Not Included

The following are intentionally not included in this public artifact:

- API keys and `src/llm_settings/llm_config.json`
- CodeQL databases, OP-TEE build trees, cache directories, and generated compile
  command files
- local notebook metadata from the private workspace
- legacy SCIS comparison CSV/JSON files used during earlier prompt development
- taint-propagation and sanitizer-recognition labels and derived comparison
  tables

The current short paper evaluates vulnerability localization/category metrics,
DITING complementarity, prompt-ablation behavior, and candidate-chain coverage.
Taint-propagation and sanitizer-recognition scoring are therefore outside the
paper-table artifact scope.
