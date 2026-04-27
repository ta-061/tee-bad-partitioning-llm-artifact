# 正解ラベルデータ

TEE Bad Partitioning脆弱性検出の評価に使用した正解ラベルデータです。

評価指標の定義（論文原稿用）は上位READMEを参照してください。  
`/workspace/bad-partitioning-ta_groundtruth_labels/README.md`

## ファイル構成

### ground_truth_labels.csv
正解ラベル（75行分）

| カラム | 説明 |
|--------|------|
| Line Number | 脆弱性が存在する行番号 |
| Category | 脆弱性カテゴリ（英語） |
| Category_JP | 脆弱性カテゴリ（日本語） |
| Function | 脆弱性が存在する関数名 |
| Label ID | ラベル識別子 |
| Group | 脆弱性グループ名 |

### partial_match_lines.csv
部分一致として許容する行の定義

| カラム | 説明 |
|--------|------|
| Detected Line | 検出された行番号 |
| Related Ground Truth Line | 関連する正解ラベルの行番号 |
| Description | 説明 |

## 脆弱性カテゴリ

| カテゴリ | 日本語名 | 行数 |
|---------|----------|------|
| unencrypted_data_output | 未暗号化出力 | 21 |
| input_validation_weakness | 入力検証不足 | 28 |
| direct_usage_of_shared_memory | 共有メモリ不適切利用 | 26 |
