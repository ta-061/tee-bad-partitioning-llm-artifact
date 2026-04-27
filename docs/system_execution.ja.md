# システム実行手順

この artifact には、公開済み LLM 出力を生成した TEE Flow Inspector の実装も含めています。

## 含めた実行系

- `src/`: 解析パイプライン本体
- `rules/`: ルール定義と DITING/CodeQL クエリ
- `prompts/`: e 系列プロンプト
- `benchmark/partitioningE/bad-partitioning/`: 実行コマンド用の最小ベンチマークパス
- `bad-partitioning-ta_groundtruth_labels/`: 正解ラベルと taint/sanitizer ラベル
- `bad-partitiont-ta_actual_evaluation/`: 実評価集計スクリプト
- `bad-partitiont-ta_pronpt_renovation/`: プロンプト改良評価スクリプト

巨大な OP-TEE ビルド生成物や CodeQL DB は除外しています。

## 環境

元の実験では `.devcontainer/` と `docker/` の Docker/DevContainer 環境を使いました。

コンテナ内では `llm_config` が使えます。ローカル環境では次のように実行できます。

```bash
PYTHONPATH=src python3 -m llm_settings.llm_cli status
PYTHONPATH=src python3 -m llm_settings.llm_cli configure openai
PYTHONPATH=src python3 -m llm_settings.llm_cli test
```

依存関係は `requirements.txt` と `docker/requirements.txt` にあります。

メイン解析器は libclang を使います。Dockerfile では LLVM/libclang 18 と
`python3-clang-18` を入れているため、再現性を重視する場合はコンテナ利用が前提です。

## LLM 設定

APIキーはコミットしません。テンプレートから作成します。

```bash
cp src/llm_settings/llm_config.example.json src/llm_settings/llm_config.json
```

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

```bash
BASE_DIR="benchmark/partitioningE/bad-partitioning/ta/e12"
OUT_BASE="bad-partitiont-ta_actual_evaluation/e12_5runs"
GT="bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv"
PM="bad-partitioning-ta_groundtruth_labels/category_labels/partial_match_lines.csv"
LABELS="bad-partitioning-ta_groundtruth_labels/flow_labels/taint_sanitizer_labels"
DITING="src/metrics/DITING_ans.csv"

for model_dir in "$BASE_DIR"/*; do
    model_name=$(basename "$model_dir")
    out_dir="$OUT_BASE/$model_name"
    python3 bad-partitiont-ta_actual_evaluation/run_actual_evaluation.py \
        --no-group-merge \
        --ground-truth "$GT" \
        --partial-match "$PM" \
        --labels-dir "$LABELS" \
        --diting-csv "$DITING" \
        --diting-projects "bad-partitioning" \
        --output-dir "$out_dir" \
        "$model_dir"
done
```

公開artifact内の集計済みデータから論文用表を再生成する場合は次を実行します。

```bash
python3 scripts/generate_paper_tables.py --check
```

このスクリプトは `data/actual_evaluation/e12_5runs/` と
`data/prompt_ablation/experiments/` を読みます。
