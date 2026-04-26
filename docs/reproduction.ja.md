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
results/tables/prompt_refinement.csv
results/tables/paper_tables.md
```

## 論文中の表との対応

- 論文 Table I: `results/tables/main_metrics_and_union.csv`
- カテゴリ別詳細: `results/tables/category_metrics.csv`
- チェーンカバレッジ: `results/tables/chain_coverage.csv`
- 論文 Table II: `results/tables/prompt_refinement.csv`

## LLM API の再実行について

この artifact は LLM API の再実行環境ではありません。API キーや各サービスの設定は含めず、論文で使った出力 JSON/CSV を保存し、そこから集計値を再生成できるようにしています。
