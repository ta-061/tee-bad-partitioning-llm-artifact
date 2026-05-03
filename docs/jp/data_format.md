# Data Format

## 正解ラベル

`benchmark/partitioningE_bad_partitioning/labels/ground_truth_labels.csv` には、1 行につき 1 つの脆弱性ラベルが入っています。

重要な列:

- `Line Number`: `benchmark/partitioningE_bad_partitioning/ta/entry.c` 内の source line
- `Category`: `unencrypted_data_output`, `input_validation_weakness`, `direct_usage_of_shared_memory` のいずれか
- `Function`: ラベル対象行を含む関数
- `Label ID`: 手作業アノテーション時の label identifier
- `Group`: 関連ラベルをまとめる coarse group

`partial_match_lines.csv` は、detector が同じ処理範囲の近傍行を報告した場合に、どの検出行をどの ground-truth line と等価に扱うかを定義します。

## Actual Evaluation Data

`data/actual_evaluation/e12_5runs/` には、評価対象モデルごとの subdirectory があります。各 model directory には以下が含まれます。

- `summary.json`: 5 回実行と consensus voting 後の aggregate metrics
- `coverage_summary.json`: Phase 3/4 function-chain coverage
- `per_run_metrics.csv`: run ごとの metrics
- `consensus_pair_votes.csv`: line/category の consensus vote
- `diting_llm_prediction_overlap.csv`: DITING と LLM prediction の overlap
- `diting_llm_gt_pair_breakdown.csv`: ground-truth label 上での overlap

表再生成スクリプトは `summary.json` と coverage fields を読みます。taint propagation / sanitizer recognition の evaluation fields は、短報の表 release からは意図的に除外しています。

重要な `summary.json` section:

- `target_scores.vulnerability_all.strict_line_category`: model F1 に使う main line+category metric
- `target_scores.vulnerability_all.line_hit_category_precision`: line hit のうち category も合っている割合
- `target_scores.vulnerability_by_category`: UDO, IVW, DUS の category metrics
- `diting_complementarity`: LLM-only, DITING-only, union metrics
- `coverage`: `chain_coverage.csv` に使う candidate-chain coverage

## Prompt Ablation Data

`data/prompt_ablation/experiments/` には、`e00_v5_1_baseline` から `e12_general_sink_screening` までの e 系列 prompt version が含まれます。

各 directory には、`summary.json`、category metrics、coverage information、supporting CSV files が含まれます。legacy SCIS comparison files と taint/sanitizer comparison files は、現在の論文表では使わないため除外しています。

`data/prompt_ablation/raw_runs/` には、e 系列 prompt experiment に対応する 1-run detector outputs が含まれます。archived されている場合は、candidate flows、sinks、vulnerability JSON、prompt/response transcripts も含まれます。

`e09c_call_forwarding_plus_recal` directory は、archived evaluation output で使われていた spelling を保持しています。対応する prompt directory は `prompts/e09c_call_forwarding_plus_recall/` です。

## Derived Databases and Tables

`data/derived_databases/` には、直接確認するための SQLite snapshot があります。

- `consensus_results_e12_5runs.db`: ground truth、DITING detections、model metadata、line/category consensus votes
- `chain_coverage_e12_5runs.db`: run ごとの candidate-chain coverage と END review rows

主な tables:

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

`results/source_tables/` には、確認用の Markdown 表コピーがあります。`results/source_tables/` 直下の compact files は clean な summary です。`original_aggregation_workspace/` subdirectory には、元の集計用ワークスペースからコピーしたより詳細な snapshot が入っています。これらの snapshot には、短報の表では使わない extra columns が含まれる場合があります。

## Prompts

`prompts/` には e 系列 prompt files が入っています。最終的な論文設定は `e12_general_sink_screening` です。
