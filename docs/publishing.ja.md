# 公開前チェックリスト

このリポジトリは、非公開の開発用リポジトリとは分けた、公開用の小さな artifact リポジトリです。

GitHub で public にする前に、次を確認してください。

1. 表を再生成する。

   ```bash
   python3 scripts/generate_paper_tables.py --check
   ```

2. ローカル絶対パスが残っていないか確認する。

   ```bash
   rg '[/]Users|[n]owstudy|[O]bsidian|04_[I]nBox|集計[用]'
   ```

   `/workspace` は Docker/DevContainer 内の作業ディレクトリとして使うため、残っていて問題ありません。

3. API キーや秘密情報が残っていないか確認する。

   ```bash
   rg 'API_[K]EY|sk-[A-Za-z0-9]|[s]ecret|[t]oken|[p]assword'
   ```

   プロンプト本文で脆弱性説明の用語として一致するものは自然です。実際の API キーや認証情報が出ないことを確認してください。

4. GitHub に新しい public repository を作る。

   ```bash
   gh repo create ta-061/tee-bad-partitioning-llm-artifact --public --source . --remote origin --push
   ```

推奨リポジトリ名は `tee-bad-partitioning-llm-artifact` です。引用しやすく、TEE の bad partitioning 評価 artifact であることが分かります。
