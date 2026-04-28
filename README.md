# TEE Bad Partitioning LLM Artifact

This repository is a reproducibility artifact for a short paper on the
complementarity of rule-based and LLM-based taint analysis for bad partitioning
issues in Trusted Applications (TAs).

日本語で読みたい場合は [README.ja.md](README.ja.md) を参照してください。

## Scope

The artifact contains curated data needed to inspect and regenerate the
paper-facing experimental tables, plus e-series results retained for full-paper
analysis:

- the evaluated TA source file from PartitioningE-Bench,
- manually curated ground-truth labels,
- DITING output used as the rule-based baseline,
- all e-series prompt versions used in the prompt-refinement experiments,
- consensus evaluation outputs for nine LLMs,
- the TEE Flow Inspector implementation used to produce the outputs,
- scripts to regenerate the main tables from the released JSON/CSV files.
- SQLite snapshots and clean Markdown summaries of the final aggregate tables.

The Docker/DevContainer runtime can rerun the LLM analysis, but rerunning it
requires a valid API key for the selected LLM provider. The archived LLM outputs
and aggregate JSON/CSV files are also included so that the reported metrics can
be checked without private API keys or paid services.

## Repository Layout

```text
benchmark/
  partitioningE_bad_partitioning/
    ta/                       # evaluated TA source file
    labels/                   # ground-truth labels and partial-match map
    diting/                   # DITING baseline output used in evaluation
  partitioningE/bad-partitioning/
    ta/                       # compact runtime-compatible benchmark path

prompts/                      # e-series prompt versions
src/                          # TEE Flow Inspector implementation
rules/                        # rule definitions and query references
docker/                       # runtime dependency and container files
configs/                      # paper model matrix and safe config references

data/
  actual_evaluation/e12_5runs/ # five-run consensus evaluation for nine models
  prompt_ablation/             # e-series prompt-refinement experiments and raw runs
  derived_databases/            # SQLite snapshots used for inspection

scripts/
  generate_paper_tables.py     # regenerates CSV/Markdown tables

results/
  tables/                      # regenerated tables written by the script
  source_tables/               # clean Markdown copies of aggregate tables

docs/
  artifact_inventory.md
  reproduction.md
  data_format.md
  system_execution.md
  publishing.md
  known_limitations.md
```

## Quick Start

The runtime path is Docker/DevContainer based. The container installs libclang,
the Python dependencies, and the `llm_config` helper.

Rerunning the LLM pipeline requires an API key. The default example
configuration uses OpenAI and `gpt-5-mini-2025-08-07`; use an OpenAI API key for
the commands below, or configure another provider with `llm_config`.

```bash
docker compose -f .devcontainer/docker-compose.yml up -d --build
docker exec -it tee-bad-partitioning-llm-artifact_devcontainer-latte-dev-1 bash
```

Inside the container:

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

When `llm_config configure openai` prompts for an API key, answer `y` and paste
your key. The template already sets the paper-style runtime defaults
(`temperature=0.2`, no OpenAI reasoning setting, JSON output). If you keep those
defaults, answer `N` to the remaining update prompts. The generated
`src/llm_settings/llm_config.json` is ignored by Git and must not be committed.

The analysis writes outputs under:

```text
benchmark/partitioningE/bad-partitioning/ta/<model-name>/results_N/
```

For table regeneration from the released archived data, use Python 3.10 or
newer:

```bash
python3 scripts/generate_paper_tables.py --check
```

The command writes regenerated tables to:

```text
results/tables/
```

The main outputs are:

- `results/tables/main_metrics_and_union.csv`
- `results/tables/category_metrics.csv`
- `results/tables/chain_coverage.csv`
- `results/tables/all_prompt_ablation.csv`
- `results/tables/prompt_refinement.csv`
- `results/tables/paper_tables.md`

Additional inspection artifacts are:

- `data/derived_databases/consensus_results_e12_5runs.db`
- `data/derived_databases/chain_coverage_e12_5runs.db`
- `results/source_tables/generated_results_tables_e12_5runs.md`
- `results/source_tables/generated_prompt_ablation_tables.md`

## What Can Be Reproduced

The script regenerates the paper-level tables for:

- main LLM-vs-DITING metrics after five-run majority voting,
- DITING and LLM union results,
- category-level metrics for UDO, IVW, and DUS,
- Phase 3 chain coverage,
- all e-series prompt-refinement results from e00 through e12,
- the paper-facing prompt-refinement subset for e03, e09c, e10, e11, and e12.

## Data Provenance

The evaluated TA comes from PartitioningE-Bench:

<https://github.com/CharlieMCY/PartitioningE-in-TEE>

The included benchmark source and DITING-derived outputs are redistributed only
for reproducibility. Please check the upstream project for its license terms.

## Notes on Paths

Some original JSON/CSV files were generated in local workspaces. Local absolute
paths have been replaced with placeholders such as `<SOURCE_REPO>` and
`<ANALYSIS_WORKSPACE>` where possible. These paths are provenance metadata and
are not required for table regeneration.

The real `src/llm_settings/llm_config.json` file is excluded because it contains
runtime credentials. Use `src/llm_settings/llm_config.example.json` as the safe
template.

See [docs/publishing.md](docs/publishing.md) for the pre-publication checklist.
See [docs/system_execution.md](docs/system_execution.md) for runtime commands.
See [docs/artifact_inventory.md](docs/artifact_inventory.md) for what is kept
and what is intentionally excluded.

## License

The scripts and documentation in this artifact are released under the MIT
License. Third-party benchmark materials are subject to their original license
terms.
