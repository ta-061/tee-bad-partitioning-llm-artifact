# Publishing Checklist

This repository is intended to be published as a compact artifact repository,
separate from the private development repository.

Before making the GitHub repository public:

1. Regenerate the tables.

   ```bash
   python3 scripts/generate_paper_tables.py --check
   ```

2. Check that no local absolute paths remain.

   ```bash
   rg '[/]Users|[n]owstudy|[O]bsidian|04_[I]nBox|集計[用]'
   ```

   The literal `/workspace` path is expected in Docker/DevContainer commands and
   scripts.

3. Check that no credentials or runtime secrets are present.

   ```bash
   rg 'API_[K]EY|sk-[A-Za-z0-9]|[s]ecret|[t]oken|[p]assword'
   ```

   Matches in prompt text are expected when they are vulnerability-domain terms.
   Actual API keys or credentials should not be present.

4. Create a new public GitHub repository, for example:

   ```bash
   gh repo create ta-061/tee-bad-partitioning-llm-artifact --public --source . --remote origin --push
   ```

The recommended repository name is `tee-bad-partitioning-llm-artifact`. It is
short enough for citation and explicit about the benchmark task.
