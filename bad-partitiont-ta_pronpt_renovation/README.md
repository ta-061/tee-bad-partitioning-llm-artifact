# Prompt Renovation Evaluation

This directory contains a script to evaluate one prompt-tuning run, or batch-evaluate all child experiment directories under a root, and compare them against the SCIS2026 `gpt-5-mini` baseline with the same gold labels.

## Script

- `run_prompt_renovation_eval.py`

## Default references

- Category labels: `/workspace/bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv`
- Partial-match map: `/workspace/bad-partitioning-ta_groundtruth_labels/category_labels/partial_match_lines.csv`
- Taint/Sanitizer labels: `/workspace/bad-partitioning-ta_groundtruth_labels/flow_labels/taint_sanitizer_labels`
- SCIS baseline vulnerabilities: `/workspace/SCIS2026-bad-partitioning-ta_LLMs_output/gpt5-mini-bad-partitioning/gpt-5-mini-ta_vulnerabilities.json`
- SCIS baseline conversations: `/workspace/SCIS2026-bad-partitioning-ta_LLMs_output/gpt5-mini-bad-partitioning/gpt-5-mini-conversations.jsonl`
- DITING answers: `/workspace/src/metrics/DITING_ans.csv`

## Usage

```bash
python3 /workspace/bad-partitiont-ta_pronpt_renovation/run_prompt_renovation_eval.py \
  /workspace/evaluation_processing/Ablation_ex_gpt-5-mini-2025-08-07/v4
```

Batch usage:

```bash
python3 /workspace/bad-partitiont-ta_pronpt_renovation/run_prompt_renovation_eval.py \
  /workspace/benchmark/partitioningE/bad-partitioning/ta/experiments \
  --output-dir /workspace/bad-partitiont-ta_pronpt_renovation/old_experiments
```

When the input path itself is not a single run directory but contains evaluable child directories, the script switches to batch mode automatically and writes:

- `/workspace/bad-partitiont-ta_pronpt_renovation/old_experiments/<child_name>/...`
- `/workspace/bad-partitiont-ta_pronpt_renovation/old_experiments/batch_summary.csv`
- `/workspace/bad-partitiont-ta_pronpt_renovation/old_experiments/batch_summary.json`

Input run directories can contain any of these conversation files:

- `conversations.jsonl`
- `ta_conversations.jsonl`
- `conversations.json`
- `ta_conversations.json`

Input run directories can contain either vulnerability format:

- original format: `ta_vulnerabilities.json` with `vulnerabilities` + `structural_risks`
- processed format: `ta_vulnerabilities.json` with `merged_by_line`

## Main outputs

- `summary.json`
  - `current_metrics.vulnerability_all.strict_line_category`: 行+カテゴリ集合一致（予測集合と正解集合が交差）
  - `current_metrics.vulnerability_all.line_only`: 行一致（カテゴリ無視、`other` を含む全検出行）
  - `current_metrics.vulnerability_all.line_hit_category_precision`: 行一致TP内でカテゴリも一致した割合
  - `current_metrics.vulnerability_by_category`: カテゴリ別TP/FP/FN/Precision/Recall/F1
  - `scis_metrics.*` に同じ構造でSCIS基準値
  - canonical category keys:
    - `unencrypted_data_output` (UDO)
    - `input_validation_weakness` (IVW)
    - `direct_usage_of_shared_memory` (DUS)
- `scis_scores.json`
- `category_metrics_comparison.csv`
- `ground_truth_hit_comparison.csv`
- `prediction_diffs.csv`
- `taint_sanitizer_comparison.csv`

## DITING complementarity

By default (if `DITING_ans.csv` exists), this script also compares current LLM run vs DITING:

- `summary.json > diting_complementarity`
  - `llm_only`, `diting_only`, `combined_union` metrics
  - overlap buckets on GT (`both`, `llm_only`, `diting_only`, `neither`)
  - gain when combining detections
- `diting_llm_gt_pair_breakdown.csv`
  - GT 75件ごとの `llm_only / diting_only / both / neither`
- `diting_llm_bucket_characteristics.csv`
  - バケットごとの `category/function/group` 集計
- `diting_llm_prediction_overlap.csv`
  - GT外FPを含む予測オーバーラップ一覧

Options:

```bash
python3 /workspace/bad-partitiont-ta_pronpt_renovation/run_prompt_renovation_eval.py \
  /workspace/benchmark/partitioningE/bad-partitioning/ta/gpt-5-mini-2025-08-07/results_5 \
  --diting-csv /workspace/src/metrics/DITING_ans.csv \
  --diting-projects bad-partitioning,badpartitioning
```

- disable DITING: `--no-diting`
