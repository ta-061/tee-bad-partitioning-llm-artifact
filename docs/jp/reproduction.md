# 再現手順

この文書では、公開用 artifact に含まれる JSON/CSV から、論文中の主要表を作り直す方法を説明します。

ここでいう「表の再生成」とは、`data/` 以下に公開済みの summary JSON を読み、表の行をもう一度計算して、`results/tables/` に CSV/Markdown として書き出すことです。これはデータ整合性の確認です。LLM パイプラインを再実行するものではなく、LLM API も Docker も不要です。

## 必要環境

- Python 3.10 以降
- 追加の Python パッケージは不要

## 表の再生成

リポジトリのルートで以下を実行します。

```bash
python3 scripts/generate_paper_tables.py --check
```

出力先:

```text
results/tables/main_metrics_and_union.csv
results/tables/category_metrics.csv
results/tables/chain_coverage.csv
results/tables/all_prompt_ablation.csv
results/tables/prompt_refinement.csv
results/tables/paper_tables.md
```

このコマンドは公開済みの `data/` だけを読みます。LLM API は呼ばず、Docker も不要です。

入力:

```text
data/actual_evaluation/e12_5runs/*/summary.json
data/prompt_ablation/experiments/*/summary.json
```

出力:

```text
results/tables/
```

## 論文中の表との対応

- 論文 Table I: `results/tables/main_metrics_and_union.csv`
- カテゴリ別詳細: `results/tables/category_metrics.csv`
- チェーンカバレッジ: `results/tables/chain_coverage.csv`
- e 系列プロンプト改良の全結果: `results/tables/all_prompt_ablation.csv`
- 論文 Table II: `results/tables/prompt_refinement.csv`

## データの確認

簡単な確認コマンド:

```bash
head -n 5 bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv
head -n 5 results/tables/main_metrics_and_union.csv
sqlite3 data/derived_databases/consensus_results_e12_5runs.db '.tables'
sqlite3 data/derived_databases/chain_coverage_e12_5runs.db '.tables'
```

SQLite の確認例:

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

`.db` は確認用 snapshot です。論文表の正式な再生成元は `data/` 以下の JSON summary です。

## LLM API の再実行について

Docker/DevContainer 環境では `src/main.py` を再実行できます。ただし、新しい LLM 呼び出しには選択した provider の有効な API キーが必要です。実行コマンドは `system_execution.md` にまとめています。公開済みの集計データから表を再生成するだけなら API キーは不要です。
