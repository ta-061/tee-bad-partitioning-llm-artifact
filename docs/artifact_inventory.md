# Artifact Inventory

This document records the current inclusion policy for the public artifact.

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

Paper-facing aggregate data:

- `data/actual_evaluation/e12_5runs/`: five-run consensus metrics for nine
  models
- `data/prompt_ablation/experiments/`: e-series prompt-ablation summaries
- `data/prompt_ablation/raw_runs/`: archived one-run outputs kept for future
  full-paper analysis
- `results/tables/`: regenerated CSV/Markdown tables used by the paper
- `results/source_tables/`: clean Markdown copies of aggregate tables

Inspection databases:

- `data/derived_databases/consensus_results_e12_5runs.db`
- `data/derived_databases/chain_coverage_e12_5runs.db`

The database files are included because they are compact enough and make it
easy to inspect consensus votes, DITING overlap, and chain-coverage rows without
rerunning the aggregation scripts.

## Excluded

The following are intentionally not part of the public release:

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
paper-facing artifact scope.
