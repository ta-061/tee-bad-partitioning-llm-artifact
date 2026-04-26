# Known Limitations

- The evaluation target is a single TA from PartitioningE-Bench.
- The released artifact focuses on reproducing the paper-level aggregate
  results. It does not include private LLM API configuration.
- Some JSON files retain provenance fields from the original execution
  environment. Local absolute paths have been replaced by placeholders where
  possible.
- DITING outputs are included as baseline artifacts. Users who want to rerun
  DITING from scratch should consult the upstream DITING/PartitioningE
  repository and CodeQL setup.
- The artifact includes the e-series prompt-refinement runs. Earlier
  exploratory prompt drafts outside the e-series are not part of the compact
  release.
