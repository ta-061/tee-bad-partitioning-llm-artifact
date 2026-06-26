# PartitioningE Bad-Partitioning Benchmark Slice

This directory contains the benchmark slice used in the paper evaluation.

The TA source file comes from PartitioningE-Bench:

<https://github.com/CharlieMCY/PartitioningE-in-TEE>

Only the source and evaluation-facing labels are included here. Build products,
CodeQL databases, object files, and OP-TEE binaries are intentionally excluded
from this public artifact.

This slice is intended to be self-contained for the paper-level evaluation, but
it is not a full mirror of PartitioningE-Bench or OP-TEE. To inspect or rebuild
the complete upstream environments, clone the original repositories separately:

```bash
git clone https://github.com/CharlieMCY/PartitioningE-in-TEE.git
git clone https://github.com/OP-TEE/optee_os.git
```

The runtime-compatible copy under
`benchmark/partitioningE/bad-partitioning/ta/` includes small
OP-TEE-compatible headers and TA support files only so the compact artifact can
be parsed and rerun without a large OP-TEE build tree.

## Files

- `ta/entry.c`: evaluated TA source file
- `ta/include/hello_world_ta.h`: header required to understand the TA source
- `labels/ground_truth_labels.csv`: manual ground-truth vulnerability labels
- `labels/partial_match_lines.csv`: line-equivalence map for scoring
- `diting/diting_generated.csv`: DITING baseline output used for scoring
- `diting/diting_raw.txt`: raw DITING output retained for provenance
