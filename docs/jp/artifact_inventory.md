# Artifact Inventory

この文書では、公開 artifact に何を含めているか、各ファイル群をどう解釈すればよいかを説明します。このリポジトリには、短報の表を再生成するためのデータと、研究中に取得した補足データの両方を含めています。

## データ区分

論文表用データは、短報の表を再生成するための正式な入力です。再現手順で説明され、`scripts/generate_paper_tables.py` または評価スクリプトから読み込まれます。

補足データは、透明性、将来の full paper 解析、独立した確認のために有用な取得済み出力です。ただし、短報ですべてを説明しているわけではありません。補足データには理解に必要な来歴を残しますが、各補足ファイルが短報中の表を直接支えるものだとは解釈しないでください。

## 含めたもの

実行系とベンチマーク:

- `src/`: LLM パイプラインで使った TEE Flow Inspector 実装
- `prompts/`: 最終 e12 設定を含む e 系列プロンプト
- `benchmark/partitioningE/bad-partitioning/`: 実行コマンド用の最小 TA ベンチマークパス
- `.devcontainer/` と `docker/`: 再現用コンテナ環境
- `src/llm_settings/llm_config.example.json`: 安全な設定テンプレート

正解ラベルとベースライン:

- `bad-partitioning-ta_groundtruth_labels/category_labels/`
- `bad-partitioning-ta_groundtruth_labels/flow_labels/ta_candidate_flows.json`
- `benchmark/partitioningE_bad_partitioning/labels/`
- `benchmark/partitioningE_bad_partitioning/diting/`
- `src/metrics/DITING_ans.csv`

論文表用の集計データ:

- `data/actual_evaluation/e12_5runs/`: 9 モデルの 5-run 多数決 metrics
- `data/prompt_ablation/experiments/`: e 系列 prompt ablation summary
- `results/tables/`: 論文で使う CSV/Markdown 表の再生成先
- `results/source_tables/`: 確認用の Markdown 表コピー
- `results/source_tables/original_aggregation_workspace/`: 元の集計用ワークスペースからコピーした、より詳細な Markdown 表 snapshot。ローカルパスや private note metadata は削除または置換済み

補足データ:

- `data/prompt_ablation/raw_runs/`: 将来の full paper 解析と来歴確認のために残した 1-run detector output

確認用 database:

- `data/derived_databases/consensus_results_e12_5runs.db`
- `data/derived_databases/chain_coverage_e12_5runs.db`

これらの database は、集計スクリプトを再実行しなくても consensus vote、DITING overlap、chain coverage の行を確認しやすくするために含めています。

## 含めていないもの

以下は、この公開 artifact には意図的に含めていません。

- API key と `src/llm_settings/llm_config.json`
- CodeQL database、OP-TEE build tree、cache directory、生成された compile command file
- private workspace 由来のローカル notebook metadata
- 初期 prompt 開発中に使った legacy SCIS 比較 CSV/JSON
- taint propagation / sanitizer recognition の label と派生比較表

現在の短報では、脆弱性の localization/category metrics、DITING との相補性、prompt ablation、candidate-chain coverage を評価しています。そのため、taint propagation と sanitizer recognition の scoring は論文表用 artifact の範囲外です。
