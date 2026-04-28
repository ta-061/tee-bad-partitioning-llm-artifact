# 再現手順

この文書では、公開用 artifact に含まれる JSON/CSV から、論文中の主要表を再生成する方法を説明します。

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

## 論文中の表との対応

- 論文 Table I: `results/tables/main_metrics_and_union.csv`
- カテゴリ別詳細: `results/tables/category_metrics.csv`
- チェーンカバレッジ: `results/tables/chain_coverage.csv`
- e 系列プロンプト改良の全結果: `results/tables/all_prompt_ablation.csv`
- 論文 Table II: `results/tables/prompt_refinement.csv`

## LLM API の再実行について

Docker/DevContainer 環境では `src/main.py` を再実行できます。ただし、新しい LLM 呼び出しには選択した provider の有効な API キーが必要です。実行コマンドは `docs/system_execution.ja.md` にまとめています。公開済みの集計データから表を再生成するだけなら API キーは不要です。
