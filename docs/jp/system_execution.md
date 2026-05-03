# システム実行手順

この artifact には、公開済み LLM 出力を生成した TEE Flow Inspector の実装も含めています。

## 含めた実行系

- `src/`: 解析パイプライン本体
- `rules/`: ルール定義と DITING/CodeQL クエリ
- `prompts/`: e 系列プロンプト
- `benchmark/partitioningE/bad-partitioning/`: 実行コマンド用の最小ベンチマークパス
- `bad-partitioning-ta_groundtruth_labels/`: 脆弱性評価と coverage 評価に必要な正解ラベル・candidate-flow ラベル
- `bad-partitiont-ta_actual_evaluation/`: 実評価集計スクリプト

巨大な OP-TEE ビルド生成物や CodeQL DB は除外しています。

## 環境

元の実験では `.devcontainer/` と `docker/` の Docker/DevContainer 環境を使いました。

コンテナは次のように起動します。

```bash
docker compose -f .devcontainer/docker-compose.yml up -d --build
docker exec -it tee-bad-partitioning-llm-artifact_devcontainer-latte-dev-1 bash
```

コンテナ内では `llm_config` が使えます。ローカル環境では次のように実行できます。

```bash
PYTHONPATH=src python3 -m llm_settings.llm_cli status
PYTHONPATH=src python3 -m llm_settings.llm_cli configure openai
PYTHONPATH=src python3 -m llm_settings.llm_cli test
```

依存関係は `requirements.txt` と `docker/requirements.txt` にあります。

メイン解析器は libclang を使います。Dockerfile では LLVM/libclang 18 と
`python3-clang-18` を入れているため、再現性を重視する場合はコンテナ利用が前提です。

この compact artifact には完全な OP-TEE dev kit は含めていません。代わりに、公開ベンチマークを巨大なビルドツリーなしでパースできるよう、
`benchmark/partitioningE/bad-partitioning/ta/include/` に最小ヘッダスタブを入れています。`make clean` 時に `TA_DEV_KIT_DIR` が見つからない警告が出るのは、この compact 構成では想定内です。

## LLM 設定

`src/main.py` で LLM 解析を再実行するには、選択した LLM provider の API キーが必要です。公開済みの集計表を再生成するだけなら API キーは不要ですが、新しい LLM 検出実行には API キーが必須です。

APIキーはコミットしません。テンプレートから作成します。

```bash
cp src/llm_settings/llm_config.example.json src/llm_settings/llm_config.json
llm_config configure openai
llm_config set openai
llm_config status
llm_config test
```

`llm_config configure openai` では、API キー更新の質問に `y` と答えてキーを貼り付けます。example ファイルには artifact の smoke test で使った実行既定値が入っています。変更しない場合は残りの更新質問には `N` と答えます。他の provider を使う場合は
`openai` を `claude`, `deepseek`, `openrouter`, `gemini` などに置き換え、
`configs/paper_model_matrix.csv` のモデル名に合わせます。

実験では、モデルは `llm_config` で切り替え、プロンプトは
`--prompt-version` で切り替えました。

共通設定は次の通りです。

- temperature: `0.2`
- reasoning setting: 評価モデルでは未指定
- Gemini: `thinking_level=low`

モデル対応表は `configs/paper_model_matrix.csv` にまとめています。

## メイン解析コマンド

最終 e12 プロンプト設定は次のコマンドで実行しました。

```bash
python3 src/main.py \
    -p benchmark/partitioningE/bad-partitioning \
    --prompt-version experiments/e12_general_sink_screening
```

公開コンテナでの動作確認では、このコマンドが正常に起動し、LLM に依存する解析フェーズまで進むことを確認しています。完全な新規 LLM 実行は時間がかかり、設定した provider にも依存します。完了時に期待される主な出力は
`ta_phase12.json`, `ta_sinks.json`, `ta_candidate_flows.json`,
`ta_vulnerabilities.json`, `ta_vulnerability_report.html`, `time.txt` です。

プロンプト改良実験では、`--prompt-version` を適宜変更します。

```bash
python3 src/main.py \
    -p benchmark/partitioningE/bad-partitioning \
    --prompt-version experiments/e03_line_grouped_end
```

プロンプトごとに出力先を整理する場合は `--output-root` を使います。

```bash
python3 src/main.py \
    -p benchmark/partitioningE/bad-partitioning \
    --prompt-version experiments/e12_general_sink_screening \
    --output-root experiments/e12_general_sink_screening
```

`--output-root` を指定しない場合、出力先は `llm_config` で選択中のモデル名から決まります。

## 実評価の集計

生の検出出力から多数決・正解ラベル評価を再計算するため、集計コマンドも必要です。
公開済み表は `scripts/generate_paper_tables.py` で再生成できますが、実験時の集計経路は次の通りです。

今回の公開 artifact では taint propagation / sanitizer recognition の評価は対象外にしたため、`--labels-dir` は不要です。将来その評価軸も必要な場合だけ、任意で label directory を指定します。

```bash
BASE_DIR="benchmark/partitioningE/bad-partitioning/ta"
OUT_BASE="bad-partitiont-ta_actual_evaluation/e12_5runs"
GT="bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv"
PM="bad-partitioning-ta_groundtruth_labels/category_labels/partial_match_lines.csv"
DITING="src/metrics/DITING_ans.csv"

python3 bad-partitiont-ta_actual_evaluation/run_actual_evaluation.py \
    --no-group-merge \
    --ground-truth "$GT" \
    --partial-match "$PM" \
    --diting-csv "$DITING" \
    --diting-projects "bad-partitioning" \
    --output-dir "$OUT_BASE" \
    "$BASE_DIR"
```

この集計スクリプトは、`results_*` を含む子ディレクトリを model root として自動的に batch 処理します。

公開artifact内の集計済みデータから論文用表を再生成する場合は次を実行します。

```bash
python3 scripts/generate_paper_tables.py --check
```

このスクリプトは `data/actual_evaluation/e12_5runs/` と
`data/prompt_ablation/experiments/` を読みます。

最終集計を直接確認するため、SQLite snapshot も残しています。

```text
data/derived_databases/consensus_results_e12_5runs.db
data/derived_databases/chain_coverage_e12_5runs.db
```

## Prompt-Ablation Data

e 系列 prompt-ablation outputs は以下に archive しています。

```text
data/prompt_ablation/raw_runs/
data/prompt_ablation/experiments/
```

e 系列全体の summary table は以下です。

```text
results/tables/all_prompt_ablation.csv
```
