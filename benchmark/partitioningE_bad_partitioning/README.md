# PartitioningE Bad-Partitioning Benchmark Slice

This directory contains the benchmark slice used in the paper evaluation.

The TA source file comes from PartitioningE-Bench:

<https://github.com/CharlieMCY/PartitioningE-in-TEE>

Only the source and evaluation-facing labels are included here. Build products,
CodeQL databases, object files, and OP-TEE binaries are intentionally excluded
from this public artifact.

## Files

- `ta/entry.c`: evaluated TA source file
- `ta/include/hello_world_ta.h`: header required to understand the TA source
- `labels/ground_truth_labels.csv`: manual ground-truth vulnerability labels
- `labels/partial_match_lines.csv`: line-equivalence map for scoring
- `diting/diting_generated.csv`: DITING baseline output used for scoring
- `diting/diting_raw.txt`: raw DITING output retained for provenance
