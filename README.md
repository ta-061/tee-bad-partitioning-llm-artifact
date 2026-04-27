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

It is not a full runtime environment for rerunning all LLM API calls. The raw
LLM outputs and aggregate JSON/CSV files are included so that the reported
metrics can be checked without access to private API keys or paid services.

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

scripts/
  generate_paper_tables.py     # regenerates CSV/Markdown tables

results/
  tables/                      # regenerated tables written by the script

docs/
  reproduction.md
  data_format.md
  system_execution.md
  publishing.md
  known_limitations.md
```

## Quick Start

Use Python 3.10 or newer.

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

## License

The scripts and documentation in this artifact are released under the MIT
License. Third-party benchmark materials are subject to their original license
terms.
