# プロンプト版変更履歴

各版で何を加え・何を消し・どのファイルを変更したかの一覧。
ベースは直前の版（e00→e01→e02→...の順序）。ただしe09a-dはe03/e08からの分岐。

## 概要テーブル

| 版 | ベース | 変更ファイル | Domain Adapter | 主な変更内容 |
|---|---|---|---|---|
| e00 | v5.1 | — | なし | ベースライン（v5.1のコピー） |
| e01 | e00 | system, end | なし | ENDを decomposed auditing に変更 |
| e02 | e01 | end | なし | ENDに forwarding gate（call-forwarding候補の証拠要求）を追加 |
| e03 | e02 | system, end | なし | END入力をline-group単位に変更（同一行の候補をまとめて審査） |
| e04 | e03 | system, end | なし | UDO vs IVW の tie-break ルールを追加 |
| e05 | e04 | system, end | なし | DUS/IVW/UDO の境界条件を明確化 |
| e06 | e05 | system, start, middle, end | なし | v4のカテゴリ優先ルール・promotion gateを導入 |
| e07 | e06 | system, start, middle, end | なし | e06のルールを軽量化（soft priority のみ残す） |
| e08 | e07 | end | なし | ENDを大幅に簡素化（ルール削減、minimal構成） |
| e09a | e03 | system | なし | system.txtにCALL-FORWARDING EXCLUSIONを追加 |
| e09b | e09a | end | なし | ENDにIVW/DUS disambiguation hint を追加 |
| e09c | e09b | start, middle, end | なし | START/MIDDLEに出力候補の列挙改善（per-line output指示） |
| e09d | e08+e03 | start, middle, end | なし | e08のminimal END + e03のSTART/MIDDLE + call-forwarding除外 |
| e10 | e09c | sink, system, start, middle, end, +domain | あり（新規） | 全ファイルをdomain-agnostic frameworkにリファクタリング、ドメイン知識をdomain adapterに分離 |
| e11 | e10 | system, start, middle, end, domain | あり（更新） | DUS列挙指示の具体化、プロンプト重複の削減、制約の簡素化 |
| e12 | e11 | sink | あり（変更なし） | Phase 3 の sink screening を write-heavy な sink 判定から汎用 taint-relevant endpoint screening に変更 |

## 各版の詳細

### e00_v5_1_baseline
- **ベース**: initial_concept/v5.1
- **目的**: 実験シリーズのベースライン確立
- **変更**: なし（そのままコピー）
- **ファイル**: system(70行), start(54行), middle(50行), end(109行)

### e01_decomposed_end
- **ベース**: e00
- **変更ファイル**: system.txt, taint_end.txt
- **追加**: ENDをdecomposed auditing方式に変更
- **削除**: e00のEND構造
- **仮説**: 分割審査によりカテゴリ安定性が向上する
- **ファイル**: system(70行), start(54行), middle(50行), end(118行, +9行)

### e02_forwarding_gate
- **ベース**: e01
- **変更ファイル**: taint_end.txt のみ
- **追加**: call-forwarding候補に対する具体的メカニズムの証拠要求
- **削除**: なし
- **仮説**: FPの多くがcall-forwarding行由来であり、証拠要求で削減できる
- **ファイル**: end(111行, -7行)

### e03_line_grouped_end
- **ベース**: e02
- **変更ファイル**: system.txt, taint_end.txt
- **追加**: END入力をline-group単位に変更（同一file:lineの候補をまとめて審査）
- **削除**: e02のforwarding gate構造
- **仮説**: 同一行の競合候補を一括審査することで整合性が向上する
- **ファイル**: system(70行), end(114行, +3行)
- **備考**: 以降e04-e08の基盤となった版

### e04_udo_tiebreak_line_grouped
- **ベース**: e03
- **変更ファイル**: system.txt, taint_end.txt
- **追加**: UDO vs IVW の tie-break ルール（情報漏洩が明確な場合はUDOを優先）
- **ファイル**: system(71行, +1行), end(117行, +3行)

### e05_line_grouped_boundary_clarification
- **ベース**: e04
- **変更ファイル**: system.txt, taint_end.txt
- **追加**: DUS/IVW/UDOの境界条件を明確化（e03の5-run分析に基づく）
- **削除**: e04のtie-breakルール
- **仮説**: カテゴリ優先ルールより境界条件の明確化の方が効果的
- **ファイル**: system(72行, +1行), end(119行, +2行)

### e06_line_grouped_v4_priority
- **ベース**: e05
- **変更ファイル**: system.txt, taint_start.txt, taint_middle.txt, taint_end.txt（全4ファイル）
- **追加**: v4のカテゴリ優先ルール、promotion gate、contrastive reasoning
- **削除**: e05の境界条件
- **仮説**: v4の分類ロジックをe03の審査単位と組み合わせる
- **ファイル**: system(71行), start(54行), middle(52行, +2行), end(124行, +5行)
- **備考**: 初めてSTART/MIDDLEも変更

### e07_line_grouped_soft_priority
- **ベース**: e06
- **変更ファイル**: system.txt, taint_start.txt, taint_middle.txt, taint_end.txt（全4ファイル）
- **追加**: IVW/DUSとUDO/IVWの軽量な優先ルールのみ
- **削除**: e06のpromotion gateと強い制約
- **仮説**: e06は過修正であり、軽量ルールのみで十分
- **ファイル**: system(70行, -1行), start(54行), middle(50行, -2行), end(120行, -4行)

### e08_minimal_end
- **ベース**: e07
- **変更ファイル**: taint_end.txt のみ
- **追加**: minimal構成のEND（役割 + 定義 + 出力形式のみ）
- **削除**: END内のルール・制約を大幅に削減
- **仮説**: e04-e07で追加したルールは全て性能を悪化させた。最小限の指示の方がLLMは自由に推論できる
- **ファイル**: end(72行, -48行)
- **備考**: ENDが最も短い版

### e09a_call_forwarding_fix
- **ベース**: e03（e08ではなくe03に戻る）
- **変更ファイル**: system.txt のみ
- **追加**: CALL-FORWARDING EXCLUSION段落をsystem.txtに追加
- **削除**: なし
- **仮説**: e03の22件のFPのうち10件がcall-forwarding行。system.txtでの除外で削減可能
- **ファイル**: system(75行, +5行)
- **備考**: e09系はe03からの分岐

### e09b_call_forwarding_plus_category
- **ベース**: e09a
- **変更ファイル**: taint_end.txt のみ
- **追加**: IVW/DUS disambiguation hint（「主なリスクが未検証サイズならIVWを優先」）
- **仮説**: call-forwarding FPに加え、4件のDUS→IVWカテゴリ誤分類を修正
- **ファイル**: end(116行, +2行)

### e09c_call_forwarding_plus_recall
- **ベース**: e09b
- **変更ファイル**: taint_start.txt, taint_middle.txt, taint_end.txt
- **追加**: START/MIDDLEに「snprintf/memcpy/TEE_MemMoveの出力行を各行個別に候補として報告する」指示
- **追加**: START/MIDDLEに「call-forwarding行は候補にしない」指示
- **削除**: e09bのEND disambiguation hint
- **仮説**: 6件のTP喪失はSTART/MIDDLEで候補として生成されなかったことが原因。候補生成の網羅性を改善
- **ファイル**: start(56行, +2行), middle(52行, +2行), end(114行, -2行)
- **備考**: FP削減とTP改善を同時に達成

### e09d_minimal_end_plus_fix
- **ベース**: e08のEND + e03のSTART/MIDDLE
- **変更ファイル**: system.txt, taint_start.txt, taint_middle.txt, taint_end.txt
- **追加**: e08のminimal ENDをcall-forwarding除外と組み合わせ
- **仮説**: e08がうまくいかなかったのはcall-forwarding FPのせい。除外すればminimal ENDも機能するはず
- **ファイル**: system(75行), start(54行), middle(50行), end(72行)

### e10_modular_framework
- **ベース**: e09c
- **変更ファイル**: 全6ファイル（sink, system, start, middle, end + domain adapter新規追加）
- **追加**: domain_optee_bad_partitioning.txt（ドメイン固有知識の設定ファイル）
- **追加**: system.txtに{placeholder}記法による抽象化
- **変更**: sinks_prompt/sink_identification.txt も OP-TEE 固有表現から domain-agnostic な表現へ一般化
- **変更**: 全プロンプトをdomain-agnosticな表現に書き換え（具体的なAPI名→プレースホルダ参照）
- **仮説**: e09cの精度を維持しつつ、ドメイン知識を差し替え可能なmodular構成にする
- **ファイル**: system(89行, +14行), start(56行), middle(52行), end(97行, -17行), domain(新規)
- **備考**: 構造的な転換点。全ファイルが大幅に変更されている

### e11_streamlined_framework
- **ベース**: e10
- **変更ファイル**: 全5ファイル（system, start, middle, end, domain adapter）
- **追加**: DUS候補生成の明示的な列挙指示（「reads, compares, decodes, or operates on shared-memory content...Emit a candidate for EACH such line individually — do not pick one representative and skip the rest」）
- **追加**: SHARED-MEMORY READ APIsセクションをdomain adapterに追加
- **追加**: IVW vs DUSのdisambiguation（共有メモリの改ざんリスクが主ならDUSを優先）
- **削除**: taint_end.txtのCATEGORY CHECKS（system.txtの定義と重複していた）
- **削除**: SELF-VERIFICATIONセクション
- **削除**: 約15個の「Do NOT」ルールを正の指示に統合
- **削除**: 冗長な「No prose」の繰り返し
- **仮説**: e10のDUS検出低下は(a)DUSの候補生成指示がなかった、(b)冗長なルールがコンテキストを圧迫した
- **ファイル**: system(24行, -65行), start(52行, -4行), middle(47行, -5行), end(52行, -45行), domain(更新)
- **備考**: system.txtが89行→24行に大幅削減。END も97行→52行に。e12 の直前版

### e12_general_sink_screening
- **ベース**: e11
- **変更ファイル**: sinks_prompt/sink_identification.txt のみ
- **追加**: 「read / write / compare / transform」を含む汎用 taint-relevant endpoint screening
- **追加**: security-relevant data を扱うパラメータの role 記述を許可
- **削除**: memcpy-like / printf-like / persistent-write などの write-heavy な sink family 列挙
- **削除**: 書き込み先 sink を前提とした過度に具体的な除外規則
- **仮説**: Phase 5 を変えずに Phase 3 の screening 幅だけを広げることで、候補カバレッジと DUS 系の再現率を改善する
- **ファイル**: sink(21行, -8行), system(24行), start(52行), middle(47行), end(52行), domain(変更なし)
- **備考**: e11 と差分があるのは sink_identification.txt のみ

## ファイルサイズ推移
| 版 | sink | system | start | middle | end | domain | 合計 |
|---|---:|---:|---:|---:|---:|---:|---:|
| e00 | 29 | 70 | 54 | 50 | 109 | — | 312 |
| e01 | 29 | 70 | 54 | 50 | 118 | — | 321 |
| e02 | 29 | 70 | 54 | 50 | 111 | — | 314 |
| e03 | 29 | 70 | 54 | 50 | 114 | — | 317 |
| e04 | 29 | 71 | 54 | 50 | 117 | — | 321 |
| e05 | 29 | 72 | 54 | 50 | 119 | — | 324 |
| e06 | 29 | 71 | 54 | 52 | 124 | — | 330 |
| e07 | 29 | 70 | 54 | 50 | 120 | — | 323 |
| e08 | 29 | 70 | 54 | 50 | 72 | — | 275 |
| e09a | 29 | 75 | 54 | 50 | 114 | — | 322 |
| e09b | 29 | 75 | 54 | 50 | 116 | — | 324 |
| e09c | 29 | 75 | 56 | 52 | 114 | — | 326 |
| e09d | 29 | 75 | 54 | 50 | 72 | — | 280 |
| e10 | 29 | 89 | 56 | 52 | 97 | 67 | 390 |
| e11 | 29 | 24 | 52 | 47 | 52 | 83 | 287 |
| e12 | 21 | 24 | 52 | 47 | 52 | 83 | 279 |

## 開発の流れ

```
e00 (baseline)
 ├─ e01 (END変更: decomposed)
 │   └─ e02 (END変更: forwarding gate)
 │       └─ e03 (END変更: line-grouped) ★基盤
 │           ├─ e04 (system+END: UDO tiebreak)
 │           │   └─ e05 (system+END: 境界条件明確化)
 │           │       └─ e06 (全ファイル: v4ルール導入)
 │           │           └─ e07 (全ファイル: soft priority)
 │           │               └─ e08 (END: minimal化)
 │           │
 │           └─ e09a (system: call-forwarding除外)
 │               └─ e09b (END: IVW/DUS hint追加)
 │                   └─ e09c (start+middle: 候補生成改善) ★最良のe03系
 │                       └─ e10 (全リファクタリング: modular化) ★domain adapter導入
 │                           └─ e11 (DUS列挙具体化 + 簡素化)
 │                               └─ e12 (sink screening汎用化) ★現行版
 │
 └─ e09d (e08 END + e03 START/MIDDLE + call-forwarding除外)
```

## 主要な観察

1. **e04-e08（ルール追加系）は全てe03を下回った** — LLMに対するルール・制約の追加は検出精度を悪化させる傾向がある
2. **e09系（failure-driven改善）が最も効果的だった** — FP分析に基づくcall-forwarding除外と、FN分析に基づく候補生成改善
3. **e10のmodular化は性能への影響が限定的** — Strict F1はe09cから低下したが、DUS F1はわずかに向上
4. **e11の簡素化は Phase 5 の土台を安定化した** — ルール削減・重複排除・列挙指示の具体化により、system.txtが89→24行、ENDが97→52行に削減された
5. **e12の sink screening 汎用化が coverage を押し上げた** — e11 から sink_identification.txt だけを変更し、write-heavy な sink 判定を general screening に置き換えることで、下流の候補到達性を広げる設計になった
