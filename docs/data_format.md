# Data Format

## Ground Truth Labels

`benchmark/partitioningE_bad_partitioning/labels/ground_truth_labels.csv`
contains one labeled vulnerability line per row.

Important columns:

- `Line Number`: source line in `benchmark/partitioningE_bad_partitioning/ta/entry.c`
- `Category`: one of `unencrypted_data_output`, `input_validation_weakness`,
  or `direct_usage_of_shared_memory`
- `Function`: function containing the labeled line
- `Label ID`: label identifier used during manual annotation
- `Group`: coarse group for related labels

`partial_match_lines.csv` maps detected lines to equivalent ground-truth lines
when the detector reports a nearby line in the same processing range.

## Actual Evaluation Data

`data/actual_evaluation/e12_5runs/` contains one subdirectory per evaluated
model. Each model directory contains:

- `summary.json`: aggregate metrics after five runs and consensus voting
- `coverage_summary.json`: Phase 3/4 function-chain coverage
- `per_run_metrics.csv`: per-run metrics
- `consensus_pair_votes.csv`: line/category consensus votes
- `diting_llm_prediction_overlap.csv`: DITING and LLM prediction overlap
- `diting_llm_gt_pair_breakdown.csv`: overlap on ground-truth labels

The table-regeneration script reads `summary.json` and coverage fields.
Taint-propagation and sanitizer-recognition evaluation fields are intentionally
excluded from the paper-facing release.

Important `summary.json` sections:

- `target_scores.vulnerability_all.strict_line_category`: main line+category
  metric used for model F1
- `target_scores.vulnerability_all.line_hit_category_precision`: category
  precision among line hits
- `target_scores.vulnerability_by_category`: UDO, IVW, and DUS metrics
- `diting_complementarity`: LLM-only, DITING-only, and union metrics
- `coverage`: candidate-chain coverage used for `chain_coverage.csv`

## Prompt Ablation Data

`data/prompt_ablation/experiments/` contains the e-series prompt versions from
`e00_v5_1_baseline` through `e12_general_sink_screening`.

Each directory includes `summary.json`, category metrics, coverage information,
and supporting CSV files.
Legacy SCIS comparison files and taint/sanitizer comparison files are excluded
because they are not used by the current paper tables.

`data/prompt_ablation/raw_runs/` contains the corresponding one-run detector
outputs for the e-series prompt experiments, including candidate flows, sinks,
vulnerability JSON, and prompt/response transcripts where archived.

The `e09c_call_forwarding_plus_recal` directory preserves the spelling used in
the archived evaluation output. The corresponding prompt directory is
`prompts/e09c_call_forwarding_plus_recall/`.

## Derived Databases and Tables

`data/derived_databases/` contains SQLite snapshots for direct inspection:

- `consensus_results_e12_5runs.db`: ground truth, DITING detections, model
  metadata, and line/category consensus votes
- `chain_coverage_e12_5runs.db`: per-run candidate-chain coverage and END review
  rows

Main tables:

```text
consensus_results_e12_5runs.db
  models
  ground_truth
  diting_detections
  consensus_votes

chain_coverage_e12_5runs.db
  models
  ground_truth
  coverage_per_run
  coverage_summary
  end_reviews
```

`results/source_tables/` contains clean Markdown copies of the aggregate tables.
They are generated from the released CSV summaries and exclude local workspace
paths, private-note metadata, taint/sanitizer metrics, and legacy SCIS fields.

## Prompts

`prompts/` contains the e-series prompt files. The final paper setting
corresponds to `e12_general_sink_screening`.
