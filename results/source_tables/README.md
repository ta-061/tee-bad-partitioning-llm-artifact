# Source Table Copies

This directory contains human-readable table snapshots copied from the original
aggregation workspace.

## Files

- `generated_results_tables_e12_5runs.md`: compact, cleaned Markdown summary of
  the final nine-model, five-run aggregate results.
- `generated_prompt_ablation_tables.md`: compact, cleaned Markdown summary of
  the e-series prompt-ablation results.
- `original_aggregation_workspace/`: fuller copied Markdown outputs from the
  original aggregation workspace, with private local paths replaced by
  placeholders.

## Role in Reproduction

These files are reference copies for inspection. Some copied snapshots may
include extra columns from the original aggregation workspace that are not used
in the short paper. The authoritative paper-table outputs are regenerated under
`results/tables/` by:

```bash
python3 scripts/generate_paper_tables.py --check
```

Use `results/tables/` when checking the short-paper tables. Use this directory
when you want to inspect the fuller table snapshots from the aggregation
workspace.
