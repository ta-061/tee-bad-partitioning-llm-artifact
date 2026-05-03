# Known Limitations

- The evaluation target is a single TA from PartitioningE-Bench.
- The released artifact focuses on reproducing the paper-level aggregate
  results. It does not include private LLM API configuration.
- Some released files may be supplemental data collected during the
  study but not discussed in the short paper. The authoritative paper-table inputs
  are the files documented in `docs/en/reproduction.md` and consumed by
  `scripts/generate_paper_tables.py`.
- Candidate function-chain generation is based on the ASTs of translation units
  that libclang can parse. `src/identify_flows/core/call_graph_builder.py`
  builds function definitions and call edges from `FUNCTION_DECL` and
  `CALL_EXPR`, and `src/identify_flows/core/chain_tracer.py` traces that call
  graph backward from sinks to sources. Therefore, functions that cannot be
  parsed because of missing compile commands or header stubs, calls that cannot
  be resolved as direct `CALL_EXPR` nodes, and calls hidden behind function
  pointers, macro expansion, or conditional compilation may be absent from the
  candidate chains. Chain coverage should therefore be read as coverage over the
  generated candidate chains, not as a complete enumeration of every semantic
  call chain that may exist in the source code.
- Some JSON files retain provenance fields from the original execution
  environment. Local absolute paths have been replaced by placeholders where
  possible.
- DITING outputs are included as baseline artifacts. Users who want to rerun
  DITING from scratch should consult the upstream DITING/PartitioningE
  repository and CodeQL setup.
- The artifact includes the e-series prompt-refinement runs. Earlier
  exploratory prompt drafts outside the e-series are not part of the compact
  release.
