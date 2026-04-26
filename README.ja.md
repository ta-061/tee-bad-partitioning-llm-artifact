# TEE Bad Partitioning LLM Artifact

このリポジトリは、Trusted Application (TA) における bad partitioning issues
に対して、ルールベース解析と LLM ベースのテイント解析の相補性を評価した短報の再現用 artifact です。

基本の説明は英語版 [README.md](README.md) にあります。この日本語版は公開時の理解を助けるための補足です。

## 含まれるもの

- PartitioningE-Bench 由来の評価対象 TA ソース
- 手作業で整備した正解ラベル
- DITING のベースライン出力
- プロンプト改良比較で使った主要プロンプト
- 9 モデル、5 回実行、多数決後の評価データ
- 論文中の主要表を再生成するスクリプト

LLM API を再実行する完全な実行環境ではありません。API キーや有料サービスなしで、論文中の集計値を確認できるように、集計済み JSON/CSV とプロンプトを中心に整理しています。

## 使い方

Python 3.10 以降を想定しています。

```bash
python3 scripts/generate_paper_tables.py --check
```

出力先:

```text
results/tables/
```

主な出力:

- `main_metrics_and_union.csv`
- `category_metrics.csv`
- `chain_coverage.csv`
- `prompt_refinement.csv`
- `paper_tables.md`

## 公開時の注意

元の作業ディレクトリには CodeQL DB、ビルド生成物、個人用メモ、キャッシュが含まれていました。この artifact では、それらを除外し、再現に必要なデータとスクリプトだけを残しています。

元データに含まれていたローカル絶対パスは、可能な範囲で `<SOURCE_REPO>` や `<ANALYSIS_WORKSPACE>` などのプレースホルダに置換しています。これらは来歴情報であり、表の再生成には不要です。

公開前の確認手順は [docs/publishing.ja.md](docs/publishing.ja.md) にまとめています。

## ライセンス

この artifact のスクリプトと文書は MIT License とします。PartitioningE-Bench 由来のファイルについては、元リポジトリのライセンス条件を確認してください。
