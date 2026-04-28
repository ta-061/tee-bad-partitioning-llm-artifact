# E12 Five-Run Aggregate Tables

Clean copy derived from `results/tables/*.csv`. Taint-propagation, sanitizer-recognition, and legacy SCIS comparison fields are intentionally excluded.

## Main Metrics and DITING Union

| model | f1 | precision | catprec | tp | fp | union_f1 | union_recall | llm_only_tp | diting_only_tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| DITING | 0.833 | 0.802 | --- | 65 | 16 | --- | --- | --- | --- |
| GPT-5-mini | 0.598 | 0.525 | 0.853 | 52 | 47 | 0.749 | 0.933 | 5 | 18 |
| GPT-5.2 | 0.784 | 0.769 | 1.000 | 60 | 18 | 0.847 | 0.960 | 7 | 12 |
| Claude Sonnet 4.5 | 0.662 | 0.671 | 0.875 | 49 | 24 | 0.828 | 0.933 | 5 | 21 |
| Claude Haiku 4.5 | 0.725 | 0.730 | 0.964 | 54 | 20 | 0.852 | 0.960 | 7 | 18 |
| DeepSeek V3.2 | 0.632 | 0.613 | 0.845 | 49 | 31 | 0.819 | 0.933 | 5 | 21 |
| Gemini 3.1 Pro | 0.766 | 0.818 | 1.000 | 54 | 12 | 0.873 | 0.960 | 7 | 18 |
| Qwen3.5-27B | 0.621 | 0.643 | 0.833 | 45 | 25 | 0.829 | 0.907 | 3 | 23 |
| gemma-3-27b-it | 0.512 | 0.472 | 0.712 | 42 | 47 | 0.767 | 0.920 | 4 | 27 |
| gemma-4-31B-it | 0.736 | 0.768 | 0.946 | 53 | 16 | 0.873 | 0.960 | 7 | 19 |
## Category Metrics

| model | udo_f1 | udo_precision | udo_recall | udo_tp | udo_fp | udo_fn | ivw_f1 | ivw_precision | ivw_recall | ivw_tp | ivw_fp | ivw_fn | dus_f1 | dus_precision | dus_recall | dus_tp | dus_fp | dus_fn |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-5-mini | 0.6222 | 0.5833 | 0.6667 | 14 | 10 | 7 | 0.6667 | 0.6250 | 0.7143 | 20 | 12 | 8 | 0.5217 | 0.4186 | 0.6923 | 18 | 25 | 8 |
| GPT-5.2 | 0.6512 | 0.6364 | 0.6667 | 14 | 8 | 7 | 0.8475 | 0.8065 | 0.8929 | 25 | 6 | 3 | 0.7925 | 0.7778 | 0.8077 | 21 | 6 | 5 |
| Claude Sonnet 4.5 | 0.6667 | 0.6667 | 0.6667 | 14 | 7 | 7 | 0.7500 | 0.9000 | 0.6429 | 18 | 2 | 10 | 0.5574 | 0.4857 | 0.6538 | 17 | 18 | 9 |
| Claude Haiku 4.5 | 0.6222 | 0.5833 | 0.6667 | 14 | 10 | 7 | 0.8070 | 0.7931 | 0.8214 | 23 | 6 | 5 | 0.5763 | 0.5152 | 0.6538 | 17 | 16 | 9 |
| DeepSeek V3.2 | 0.6222 | 0.5833 | 0.6667 | 14 | 10 | 7 | 0.7111 | 0.9412 | 0.5714 | 16 | 1 | 12 | 0.5588 | 0.4524 | 0.7308 | 19 | 23 | 7 |
| Gemini 3.1 Pro | 0.6667 | 0.6667 | 0.6667 | 14 | 7 | 7 | 0.8214 | 0.8214 | 0.8214 | 23 | 5 | 5 | 0.6800 | 0.7083 | 0.6538 | 17 | 7 | 9 |
| Qwen3.5-27B | 0.6222 | 0.5833 | 0.6667 | 14 | 10 | 7 | 0.5263 | 1.0000 | 0.3571 | 10 | 0 | 18 | 0.6462 | 0.5385 | 0.8077 | 21 | 18 | 5 |
| gemma-3-27b-it | 0.5600 | 0.4828 | 0.6667 | 14 | 15 | 7 | 0.5116 | 0.7333 | 0.3929 | 11 | 4 | 17 | 0.4359 | 0.3269 | 0.6538 | 17 | 35 | 9 |
| gemma-4-31B-it | 0.6667 | 0.6667 | 0.6667 | 14 | 7 | 7 | 0.8462 | 0.9167 | 0.7857 | 22 | 2 | 6 | 0.6415 | 0.6296 | 0.6538 | 17 | 10 | 9 |
## Candidate Chain Coverage

| model | phase3_profile | sinks | chains | gt_lines | covered | uncovered | coverage_percent | uncovered_lines | uncovered_functions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| GPT-5-mini | general | 17 | 22 | 75 | 72 | 3 | 96.0 | 254,256,258 | produce_i3 |
| GPT-5.2 | general | 12 | 26 | 75 | 72 | 3 | 96.0 | 254,256,258 | produce_i3 |
| Claude Sonnet 4.5 | general | 13 | 26 | 75 | 72 | 3 | 96.0 | 254,256,258 | produce_i3 |
| Claude Haiku 4.5 | general | 8 | 22 | 75 | 72 | 3 | 96.0 | 254,256,258 | produce_i3 |
| DeepSeek V3.2 | general | 12 | 26 | 75 | 72 | 3 | 96.0 | 254,256,258 | produce_i3 |
| Gemini 3.1 Pro | general | 11 | 22 | 75 | 72 | 3 | 96.0 | 254,256,258 | produce_i3 |
| Qwen3.5-27B | general | 14 | 26 | 75 | 72 | 3 | 96.0 | 254,256,258 | produce_i3 |
| gemma-3-27b-it | general | 16 | 30 | 75 | 75 | 0 | 100.0 |  |  |
| gemma-4-31B-it | general | 12 | 22 | 75 | 72 | 3 | 96.0 | 254,256,258 | produce_i3 |
