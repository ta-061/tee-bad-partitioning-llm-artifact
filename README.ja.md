# TEE Bad Partitioning LLM Artifact

このリポジトリは、Trusted Application (TA) における bad partitioning issues
に対して、ルールベース解析と LLM ベースの脆弱性解析の相補性を評価した短報の再現用 artifact です。

基本の説明は英語版 [README.md](README.md) にあります。この日本語版は公開時の理解を助けるための補足です。

## 含まれるもの

- PartitioningE-Bench 由来の評価対象 TA ソース
- 手作業で整備した正解ラベル
- DITING のベースライン出力
- プロンプト改良比較で使った e 系列プロンプト一式
- 9 モデル、5 回実行、多数決後の評価データ
- 出力生成に使った TEE Flow Inspector 実装
- 論文中の主要表を再生成するスクリプト
- 最終集計を確認するための SQLite `.db` と clean な Markdown 集計表

Docker/DevContainer 環境では LLM 解析の再実行もできます。ただし、再実行には選択した LLM provider の有効な API キーが必要です。一方で、論文中の集計値を確認するだけなら、同梱済みの LLM 出力 JSON/CSV と集計スクリプトを使えるため、API キーは不要です。

## Quick Start

論文中の表を確認するだけなら API キーは不要です。まず以下を実行してください。

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

最終集計を直接確認する場合は、SQLite snapshot も見られます。

```bash
sqlite3 data/derived_databases/consensus_results_e12_5runs.db '.tables'
sqlite3 data/derived_databases/chain_coverage_e12_5runs.db '.tables'
```

確認の入口:

- `results/tables/paper_tables.md`: 論文向けの簡潔な表
- `results/source_tables/generated_results_tables_e12_5runs.md`: 5-run 集計表
- `results/source_tables/generated_prompt_ablation_tables.md`: e 系列 prompt ablation 表
- `data/actual_evaluation/e12_5runs/<model>/summary.json`: 各モデルの集計値
- `data/prompt_ablation/experiments/<prompt>/summary.json`: 各プロンプト版の集計値

## LLM 解析の再実行

実行系は Docker/DevContainer 前提です。コンテナ内に libclang、Python依存関係、`llm_config` が入ります。

LLM パイプラインを再実行するには API キーが必須です。初期設定例は OpenAI の
`gpt-5-mini-2025-08-07` を使います。以下の手順では OpenAI API キーを用意してください。別 provider を使う場合は `llm_config` で provider とモデルを切り替えます。

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
llm_config status
llm_config test

python3 src/main.py \
    -p benchmark/partitioningE/bad-partitioning \
    --prompt-version experiments/e12_general_sink_screening
```

`llm_config configure openai` では、API キー更新の質問に `y` と答えてキーを貼り付けます。テンプレートには論文時の実行設定に合わせた既定値
(`temperature=0.2`, OpenAI reasoning setting なし, JSON output) を入れているため、それらを変えない場合は残りの更新質問には `N` と答えます。生成される
`src/llm_settings/llm_config.json` は Git 管理外で、公開リポジトリに commit しません。

解析結果は次に出力されます。

```text
benchmark/partitioningE/bad-partitioning/ta/<model-name>/results_N/
```

新しく生成した raw output を集計する場合は、次を実行します。

```bash
python3 bad-partitiont-ta_actual_evaluation/run_actual_evaluation.py \
    --no-group-merge \
    --ground-truth bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv \
    --partial-match bad-partitioning-ta_groundtruth_labels/category_labels/partial_match_lines.csv \
    --diting-csv src/metrics/DITING_ans.csv \
    --diting-projects bad-partitioning \
    --output-dir /tmp/artifact_eval \
    benchmark/partitioningE/bad-partitioning/ta/<model-name>
```

## データ対応表

| 確認したいこと | ファイルまたはディレクトリ |
| --- | --- |
| 評価対象 TA source | `benchmark/partitioningE_bad_partitioning/ta/entry.c` と runtime copy の `benchmark/partitioningE/bad-partitioning/ta/entry.c` |
| 脆弱性正解ラベル | `bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv` |
| 近傍行を同一扱いする対応 | `bad-partitioning-ta_groundtruth_labels/category_labels/partial_match_lines.csv` |
| DITING 出力 | `src/metrics/DITING_ans.csv`, `benchmark/partitioningE_bad_partitioning/diting/diting_generated.csv` |
| 9モデル5-run集計 | `data/actual_evaluation/e12_5runs/<model>/summary.json` |
| e系列 prompt ablation 集計 | `data/prompt_ablation/experiments/<prompt>/summary.json` |
| e系列 raw output | `data/prompt_ablation/raw_runs/<prompt>/results_1/` |
| 論文用に再生成される表 | `results/tables/` |
| SQLite snapshot | `data/derived_databases/` |

## 公開時の注意

元の作業ディレクトリには CodeQL DB、ビルド生成物、個人用メモ、キャッシュが含まれていました。この artifact では、それらを除外し、再現に必要なデータとスクリプトだけを残しています。

元データに含まれていたローカル絶対パスは、可能な範囲で `<SOURCE_REPO>` や `<ANALYSIS_WORKSPACE>` などのプレースホルダに置換しています。これらは来歴情報であり、表の再生成には不要です。

実APIキーを含む `src/llm_settings/llm_config.json` は公開対象から除外し、代わりに `src/llm_settings/llm_config.example.json` を入れています。

公開前の確認手順は [docs/publishing.ja.md](docs/publishing.ja.md) にまとめています。

システム本体の実行コマンドと集計コマンドは [docs/system_execution.ja.md](docs/system_execution.ja.md) にまとめています。

何を含め、何を除外したかは [docs/artifact_inventory.md](docs/artifact_inventory.md) にまとめています。

## ライセンス

この artifact のスクリプトと文書は MIT License とします。PartitioningE-Bench 由来のファイルについては、元リポジトリのライセンス条件を確認してください。
