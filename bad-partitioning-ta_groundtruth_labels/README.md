# bad-partitioning TA Ground Truth: 評価定義（論文原稿用）

本ディレクトリは、`bad-partitioning` の評価で共通利用するゴールドラベルと評価定義を管理します。  
本READMEは、論文本文・実験節に記載する「評価指標の定義」の基準です。

## 評価対象

- カテゴリ付き脆弱性検出（行 + カテゴリ）
- 行位置のみの脆弱性検出（カテゴリ無視）
- テイント伝播認識
- サニタイザ認識

## カテゴリ定義（正規キー）

- `unencrypted_data_output` (UDO)
- `input_validation_weakness` (IVW)
- `direct_usage_of_shared_memory` (DUS)

補足:
- 旧キー（`unencrypted_output`, `weak_input_validation`, `shared_memory_overwrite`）は互換入力として受理しても、集計時は上記正規キーに正規化する。

## カテゴリ付き脆弱性評価（Strict）

正解側カテゴリ集合を `GT_cat(line)`、予測側カテゴリ集合を `Pred_cat(line)` とする。  
予測行は `Pred_line_strict`（カテゴリ無視の全検出行、`other` 含む）を使う。

- `TP_strict`: `line ∈ Pred_line_strict` かつ `Pred_cat(line) ∩ GT_cat(line) ≠ ∅`
- `FP_strict`: `line ∈ Pred_line_strict` かつ上記条件を満たさない
- `FN_strict`: GT行のうち `Pred_cat(line) ∩ GT_cat(line) = ∅`（未検出を含む）
- `Precision_strict = TP_strict / (TP_strict + FP_strict)`
- `Recall_strict = TP_strict / (TP_strict + FN_strict)`
- `F1_strict = 2 * Precision_strict * Recall_strict / (Precision_strict + Recall_strict)`

### 部分一致行の扱い

`category_labels/partial_match_lines.csv` の対応がある場合、予測行を関連GT行へ正規化してから評価する。  
カテゴリ集合は、正規化後の行に集約して比較する。

## 行のみ脆弱性評価（Line-only）

- `GT_line = {line | (line, category) ∈ GT_pair}`
- `Pred_line = {line | vulnerabilities/structural_risks または merged_by_line に含まれる全検出行}`  
  （カテゴリ無視、`other` を含む）

- `TP_line = |Pred_line ∩ GT_line|`
- `FP_line = |Pred_line - GT_line|`
- `FN_line = |GT_line - Pred_line|`

同様に Precision / Recall / F1 を計算する。

部分一致行の正規化は Line-only にも適用する（Detected Line が対応表にあれば Related Ground Truth Line へ写像）。

## 位置検出後のカテゴリ精度

- `line_hit_category_precision = TP_strict / TP_line`

意味:
- 行位置を当てた中で、カテゴリまで正しく当てた割合。

## テイント伝播評価（現行定義）

正解は `flow_labels/taint_sanitizer_labels/*_taint_labels.csv` から読み込む。  
評価単位は重複除去後の `(function, var)`。

- 変数名は正規化（配列添字などを `[*]` 化）
- 一致判定は「完全一致 or 部分一致 or ベース名一致」
- `TP_taint`: 正解側要素が少なくとも1つの予測に一致
- `FP_taint`: どの正解にも一致しない予測
- `FN_taint`: 一致しなかった正解

## サニタイザ評価（現行定義）

正解は `flow_labels/taint_sanitizer_labels/*_sanitizer_labels.csv`。  
評価単位は `(function, line)`。

- 行番号は数値抽出で解釈（例: `346-348` は `346` として扱える）
- 関数一致かつ `|pred_line - gt_line| <= tolerance` で一致（既定 `tolerance=2`）

## SCIS互換（legacy）との差分

SCIS時集計は、以下の差で値がずれることがある。

- テイント: カテゴリ別集計の合算により、重複が残る母数になりうる
- サニタイザ: 範囲表記行（例 `346-348`）を `int()` で落とす場合がある

次論文では、上記「現行定義」を主指標とし、必要に応じてSCIS互換値を併記する。

## ラベル配置

- カテゴリ評価ラベル: `category_labels/`
- テイント/サニタイザ評価ラベル: `flow_labels/taint_sanitizer_labels/`
