# Known Limitations

- 評価対象は PartitioningE-Bench 由来の 1 つの TA です。
- 公開 artifact は paper-level aggregate results の再現に焦点を当てています。private な LLM API configuration は含めていません。
- 公開ファイルの一部には、研究中に取得したものの短報では説明していない補足データが含まれます。論文表の正式な入力は、`docs/jp/reproduction.md` に記載され、`scripts/generate_paper_tables.py` が読み込むファイルです。
- 候補関数チェーンの生成は、libclang で parse できた translation unit の AST に基づきます。`src/identify_flows/core/call_graph_builder.py` は `FUNCTION_DECL` と `CALL_EXPR` から関数定義と呼び出し辺を作り、`src/identify_flows/core/chain_tracer.py` がその call graph を逆向きに辿ります。そのため、compile command や header stub の不足で parse できない関数、AST 上で直接の `CALL_EXPR` として解決できない呼び出し、関数ポインタ・macro 展開・条件付きコンパイルなどで静的に見えない呼び出しは、candidate chain に含まれない可能性があります。したがって chain coverage は「生成された候補チェーンに対する coverage」であり、ソースコード上に存在し得る全ての意味的な呼び出しチェーンを完全列挙したものではありません。
- 一部の JSON file には、元の実行環境に由来する provenance fields が残っています。ローカル絶対パスは可能な範囲で placeholder に置換しています。
- DITING outputs は baseline artifact として含めています。DITING を scratch から再実行したい場合は、upstream の DITING/PartitioningE repository と CodeQL setup を確認してください。
- この artifact には e 系列 prompt-refinement runs を含めています。e 系列より前の exploratory prompt drafts は compact release には含めていません。
