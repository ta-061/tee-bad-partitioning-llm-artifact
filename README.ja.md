# TEE Bad Partitioning LLM Artifact

このリポジトリは、Trusted Application (TA) における bad partitioning issues
に対して、ルールベース解析と LLM ベースのテイント解析の相補性を評価した短報の再現用 artifact です。

基本の説明は英語版 [README.md](README.md) にあります。この日本語版は公開時の理解を助けるための補足です。

## 含まれるもの

- PartitioningE-Bench 由来の評価対象 TA ソース
- 手作業で整備した正解ラベル
- DITING のベースライン出力
- プロンプト改良比較で使った e 系列プロンプト一式
- 9 モデル、5 回実行、多数決後の評価データ
- 出力生成に使った TEE Flow Inspector 実装
- 論文中の主要表を再生成するスクリプト

LLM API を再実行する完全な実行環境ではありません。API キーや有料サービスなしで、論文中の集計値を確認できるように、集計済み JSON/CSV とプロンプトを中心に整理しています。

## 使い方

実行系は Docker/DevContainer 前提です。コンテナ内に libclang、Python依存関係、`llm_config` が入ります。

```bash
docker compose -f .devcontainer/docker-compose.yml up -d --build
docker exec -it tee-bad-partitioning-llm-artifact_devcontainer-latte-dev-1 bash
```

コンテナ内で以下を実行します。

```bash
cd /workspace
cp src/llm_settings/llm_config.example.json src/llm_settings/llm_config.json
llm_config configure openai
llm_config set openai

python3 src/main.py \
    -p benchmark/partitioningE/bad-partitioning \
    --prompt-version experiments/e12_general_sink_screening
```

解析結果は次に出力されます。

```text
benchmark/partitioningE/bad-partitioning/ta/<model-name>/results_N/
```

公開済みの集計済みデータから表だけを再生成する場合は、Python 3.10 以降で次を実行します。

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
- `all_prompt_ablation.csv`
- `prompt_refinement.csv`
- `paper_tables.md`

## 公開時の注意

元の作業ディレクトリには CodeQL DB、ビルド生成物、個人用メモ、キャッシュが含まれていました。この artifact では、それらを除外し、再現に必要なデータとスクリプトだけを残しています。

元データに含まれていたローカル絶対パスは、可能な範囲で `<SOURCE_REPO>` や `<ANALYSIS_WORKSPACE>` などのプレースホルダに置換しています。これらは来歴情報であり、表の再生成には不要です。

実APIキーを含む `src/llm_settings/llm_config.json` は公開対象から除外し、代わりに `src/llm_settings/llm_config.example.json` を入れています。

公開前の確認手順は [docs/publishing.ja.md](docs/publishing.ja.md) にまとめています。

システム本体の実行コマンドと集計コマンドは [docs/system_execution.ja.md](docs/system_execution.ja.md) にまとめています。

## ライセンス

この artifact のスクリプトと文書は MIT License とします。PartitioningE-Bench 由来のファイルについては、元リポジトリのライセンス条件を確認してください。
