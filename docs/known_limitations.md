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
- The prompt-refinement comparison uses selected versions that are discussed in
  the paper, not every exploratory prompt version produced during development.
