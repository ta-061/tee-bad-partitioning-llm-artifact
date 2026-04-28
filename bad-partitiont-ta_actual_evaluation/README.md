# Actual Evaluation (Multi-run)

This directory contains scripts for aggregating all `results_*` runs of one model and evaluating consensus detections. The main script can also batch-process all child model directories under a parent.

## Files

- `evaluation_common.py`: shared evaluation logic
- `run_actual_evaluation.py`: per-run metrics + consensus evaluation

## Consensus rule

- Default window: latest 5 runs (`--required-runs 5`)
- Default threshold: 3 votes (`--min-votes 3`)
- Consensus applies to:
  - vulnerability `(line, category)` pairs from `ta_vulnerabilities.json`
    - supported vulnerability formats:
      - original format: `vulnerabilities` + `structural_risks`
      - processed format: `merged_by_line` (line-key merged JSON)

Taint-propagation and sanitizer-recognition scoring is optional legacy
functionality. The current paper artifact does not include those labels, so the
default run computes vulnerability, DITING complementarity, and coverage metrics
only. Provide `--labels-dir` only if you intentionally restore that optional
label set.

## Usage

```bash
python3 /workspace/bad-partitiont-ta_actual_evaluation/run_actual_evaluation.py \
  /workspace/evaluation_processing/gpt-5-mini-2025-08-07
```

Batch usage:

```bash
python3 /workspace/bad-partitiont-ta_actual_evaluation/run_actual_evaluation.py \
  /workspace/benchmark/partitioningE/bad-partitioning/ta/e11 \
  --output-dir /workspace/bad-partitiont-ta_actual_evaluation/experiments_5_runs
```

When the input path itself is not a model root but contains child model roots with `results_*`, the script switches to batch mode automatically and writes:

- `/workspace/bad-partitiont-ta_actual_evaluation/experiments_5_runs/<child_name>/...`
- `/workspace/bad-partitiont-ta_actual_evaluation/experiments_5_runs/batch_summary.csv`
- `/workspace/bad-partitiont-ta_actual_evaluation/experiments_5_runs/batch_summary.json`

## Main outputs

- `summary.json`
  - `target_scores.vulnerability_all.strict_line_category`: 行+カテゴリ集合一致（予測集合と正解集合が交差）
  - `target_scores.vulnerability_all.line_only`: 行一致（カテゴリ無視、`other` を含む全検出行）
  - `target_scores.vulnerability_all.line_hit_category_precision`: 行一致TP内でカテゴリも一致した割合
  - `target_scores.vulnerability_by_category`: カテゴリ別TP/FP/FN/Precision/Recall/F1
  - canonical category keys:
    - `unencrypted_data_output` (UDO)
    - `input_validation_weakness` (IVW)
    - `direct_usage_of_shared_memory` (DUS)
- `per_run_metrics.csv`
- `consensus_pair_votes.csv`
- `ground_truth_consensus_hits.csv`
- `consensus_category_metrics.csv`

## DITING complementarity (default enabled if CSV exists)

`run_actual_evaluation.py` now compares consensus LLM detections with DITING answers and writes:

- `diting_llm_gt_pair_breakdown.csv`
  - GT 75件の各行+カテゴリについて `llm_only / diting_only / both / neither` を確認
  - `function`, `label_id`, `group` 付きで箇所の特徴を直接確認可能
- `diting_llm_bucket_characteristics.csv`
  - 上記バケットの特徴量を `category/function/group` 単位で集計
- `diting_llm_prediction_overlap.csv`
  - GT外のFPを含む、LLMとDITINGの予測オーバーラップ一覧
- `summary.json > diting_complementarity`
  - `llm_only`, `diting_only`, `combined_union` の strict/line 指標
  - 組み合わせ時の増分 (`delta_vs_llm`, `delta_vs_diting`)
  - GT上の重なり (`both`, `llm_only`, `diting_only`, `union_gain`)

Options:

```bash
python3 /workspace/bad-partitiont-ta_actual_evaluation/run_actual_evaluation.py \
  /workspace/evaluation_processing/gpt-5-mini-2025-08-07 \
  --diting-csv /workspace/src/metrics/DITING_ans.csv \
  --diting-projects bad-partitioning,badpartitioning
```

- 無効化する場合: `--no-diting`

## Optional SCIS comparison

SCIS comparison is disabled by default and is not included in the current paper
artifact. Enable it only if you have the external baseline files locally:

```bash
python3 /workspace/bad-partitiont-ta_actual_evaluation/run_actual_evaluation.py \
  /workspace/benchmark/partitioningE/bad-partitioning/ta/gpt-5-mini-2025-08-07 \
  --with-scis \
  --scis-vuln /workspace/SCIS2026-bad-partitioning-ta_LLMs_output/gpt5-mini-bad-partitioning/gpt-5-mini-ta_vulnerabilities.json \
  --scis-conversations /workspace/SCIS2026-bad-partitioning-ta_LLMs_output/gpt5-mini-bad-partitioning/gpt-5-mini-conversations.jsonl
```
