# TEE Bad Partitioning LLM Artifact

このリポジトリは、Trusted Application (TA) における bad partitioning issues
に対して、ルールベース解析と LLM ベースの脆弱性解析の相補性を評価した短報の再現用 artifact です。

基本の説明は英語版 [README.md](README.md) にあります。この日本語版は日本語で内容を確認するための補足です。

## 含まれるもの

- PartitioningE-Bench 由来の評価対象 TA ソース
- 手作業で整備した正解ラベル
- DITING のベースライン出力
- プロンプト改良比較で使った e 系列プロンプト一式
- 9 モデル、5 回実行、多数決後の評価データ
- 出力生成に使った TEE Flow Inspector 実装
- 論文中の主要表を再生成するスクリプト
- 最終集計を確認するための SQLite `.db` と clean な Markdown 集計表

このリポジトリのデータは、論文中の表を作り直すための正式な入力データと、短報の紙幅では説明しきれなかった取得済みの補足データに分けて扱います。補足データは来歴確認や将来の full paper 解析のために公開していますが、README やスクリプトで明示的に対応付けられていない限り、論文中の表の根拠データとしては扱いません。

Docker/DevContainer 環境では LLM 解析の再実行もできます。ただし、再実行には選択した LLM provider の有効な API キーが必要です。一方で、論文中の集計値を確認するだけなら、同梱済みの LLM 出力 JSON/CSV と集計スクリプトを使えるため、API キーは不要です。

## データの見方

| 目的 | 最初に見る場所 | 補足 |
| --- | --- | --- |
| 論文中の主要表を確認する | `docs/jp/reproduction.md` または `python3 scripts/generate_paper_tables.py --check` | 公開済み JSON summary から `results/tables/` を作り直します。API キーや Docker は不要です。 |
| 表の入力集計を確認する | `data/actual_evaluation/e12_5runs/`, `data/prompt_ablation/experiments/` | 論文表を作り直すための正式な入力です。 |
| コピー済み Markdown 表を見る | `results/source_tables/README.md` | 元の集計用ワークスペースからの参照コピーです。正式な再生成結果ではありません。 |
| prompt ablation の raw output を見る | `data/prompt_ablation/raw_runs/` | 1-run の検出結果、transcript、中間JSONです。 |
| LLM パイプラインを再実行する | `docs/jp/system_execution.md` | Docker/DevContainer と LLM API キーが必要です。 |
| 含まれるデータ・除外データを確認する | `docs/jp/artifact_inventory.md`, `docs/jp/known_limitations.md` | 論文表用データと補足データの区別を説明しています。 |

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

ここでいう「再生成」は、`data/` 以下の公開済み summary JSON から CSV/Markdown の表ファイルを作り直すという意味です。LLM の再実行ではありません。

最終集計を直接確認する場合は、SQLite snapshot も見られます。

```bash
sqlite3 data/derived_databases/consensus_results_e12_5runs.db '.tables'
sqlite3 data/derived_databases/chain_coverage_e12_5runs.db '.tables'
```

確認の入口:

- 論文表の正式な出力: `results/tables/paper_tables.md`
- 正式な入力集計: `data/actual_evaluation/e12_5runs/<model>/summary.json`, `data/prompt_ablation/experiments/<prompt>/summary.json`
- 元の集計用ワークスペースからの参照コピー: `results/source_tables/README.md`

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
| コピー済み Markdown 表 | `results/source_tables/` |
| 論文表の正式な再生成経路 | `docs/jp/reproduction.md` と `scripts/generate_paper_tables.py` |
| 補足データの扱い | `docs/jp/artifact_inventory.md` |
| SQLite snapshot | `data/derived_databases/` |

## 利用上の注意

元の作業ディレクトリには CodeQL DB、ビルド生成物、個人用メモ、キャッシュが含まれていました。この artifact では、それらを除外し、再現に必要なデータとスクリプトを中心に残しています。論文本文で使わなかった取得済みデータは、論文表用データとは別の補足データとして置き、論文表の再生成には不要であることを明記します。

この artifact に含めているベンチマークファイルは、論文レベルの評価を再現するために必要な最小限のものです。PartitioningE-Bench の完全なリポジトリ、OP-TEE の build tree、OP-TEE バイナリ、CodeQL DB、生成済み build product は同梱していません。上流の完全な環境を確認または再構築したい場合は、必要に応じて元リポジトリを別途 clone してください。

```bash
git clone https://github.com/CharlieMCY/PartitioningE-in-TEE.git
git clone https://github.com/OP-TEE/optee_os.git
```

`benchmark/partitioningE/bad-partitioning/ta/` には、公開ベンチマークを大きな OP-TEE build tree なしで parse または再実行できるようにするための小さな OP-TEE 互換ヘッダと TA support file も含めています。これらは compact な再現用 artifact の一部であり、上流 OP-TEE source や dev kit 全体の代替ではありません。

元データに含まれていたローカル絶対パスは、可能な範囲で `<SOURCE_REPO>` や `<ANALYSIS_WORKSPACE>` などのプレースホルダに置換しています。これらは来歴情報であり、表の再生成には不要です。

実APIキーを含む `src/llm_settings/llm_config.json` はこの公開リポジトリから除外し、代わりに `src/llm_settings/llm_config.example.json` を入れています。

システム本体の実行コマンドと集計コマンドは [docs/jp/system_execution.md](docs/jp/system_execution.md) にまとめています。

何を含め、何を除外したかは [docs/jp/artifact_inventory.md](docs/jp/artifact_inventory.md) にまとめています。

## ライセンス

この artifact のスクリプトと文書は MIT License とします。PartitioningE-Bench 由来のファイルについては、元リポジトリのライセンス条件を確認してください。
