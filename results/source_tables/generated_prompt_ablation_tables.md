# Prompt Ablation Aggregate Tables

Clean copy derived from `results/tables/all_prompt_ablation.csv` and `results/tables/prompt_refinement.csv`. Taint-propagation, sanitizer-recognition, and legacy SCIS comparison fields are intentionally excluded.

## All E-Series Prompt Ablation Results

| version | directory | f1 | line_f1 | catprec | recall | precision | tp | fp | fn | candidate_coverage | udo_f1 | udo_tp | ivw_f1 | ivw_tp | dus_f1 | dus_tp |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| e00 | e00_v5_1_baseline | 0.3660 | 0.6144 | 0.5957 | 0.3733 | 0.3590 | 28 | 50 | 47 | 92.0 | 0.2667 | 4 | 0.5143 | 18 | 0.2000 | 6 |
| e01 | e01_decomposed_end | 0.2857 | 0.5286 | 0.5405 | 0.2667 | 0.3077 | 20 | 45 | 55 | 92.0 | 0.2500 | 4 | 0.3871 | 12 | 0.1538 | 4 |
| e02 | e02_forwarding_gate | 0.4027 | 0.5906 | 0.6818 | 0.4000 | 0.4054 | 30 | 44 | 45 | 92.0 | 0.4324 | 8 | 0.4828 | 14 | 0.2667 | 8 |
| e03 | e03_line_grouped_end | 0.4521 | 0.5890 | 0.7674 | 0.4400 | 0.4648 | 33 | 38 | 42 | 92.0 | 0.3636 | 6 | 0.5937 | 19 | 0.2581 | 8 |
| e04 | e04_udo_tiebreak_line_grouped | 0.4571 | 0.5571 | 0.8205 | 0.4267 | 0.4923 | 32 | 33 | 43 | 92.0 | 0.5946 | 11 | 0.5000 | 14 | 0.2456 | 7 |
| e05 | e05_line_grouped_boundary_clarification | 0.3947 | 0.5921 | 0.6667 | 0.4000 | 0.3896 | 30 | 47 | 45 | 92.0 | 0.2857 | 4 | 0.5135 | 19 | 0.2373 | 7 |
| e06 | e06_line_grouped_v4_priority | 0.3448 | 0.5517 | 0.6250 | 0.3333 | 0.3571 | 25 | 45 | 50 | 92.0 | 0.2857 | 5 | 0.4478 | 15 | 0.1818 | 5 |
| e07 | e07_line_grouped_soft_priority | 0.5600 | 0.5867 | 0.9545 | 0.5600 | 0.5600 | 42 | 33 | 33 | 92.0 | 0.6667 | 14 | 0.6333 | 19 | 0.2903 | 9 |
| e08 | e08_minimal_end | 0.5132 | 0.5921 | 0.8667 | 0.5200 | 0.5065 | 39 | 38 | 36 | 92.0 | 0.5714 | 12 | 0.5763 | 17 | 0.3279 | 10 |
| e09a | e09a_call_forwarding_fix | 0.3947 | 0.5526 | 0.7143 | 0.4000 | 0.3896 | 30 | 47 | 45 | 92.0 | 0.4242 | 7 | 0.4412 | 15 | 0.2623 | 8 |
| e09b | e09b_call_forwarding_plus_category | 0.3867 | 0.5733 | 0.6744 | 0.3867 | 0.3867 | 29 | 46 | 46 | 92.0 | 0.3889 | 7 | 0.4412 | 15 | 0.2500 | 7 |
| e09c | e09c_call_forwarding_plus_recal | 0.5644 | 0.6258 | 0.9020 | 0.6133 | 0.5227 | 46 | 42 | 29 | 92.0 | 0.6222 | 14 | 0.6780 | 20 | 0.3810 | 12 |
| e09d | e09d_minimal_end_plus_fix | 0.5270 | 0.5946 | 0.8864 | 0.5200 | 0.5342 | 39 | 34 | 36 | 92.0 | 0.6190 | 13 | 0.6129 | 19 | 0.2258 | 7 |
| e10 | e10_modular_framework | 0.5641 | 0.6282 | 0.8980 | 0.5867 | 0.5432 | 44 | 37 | 31 | 92.0 | 0.6222 | 14 | 0.6780 | 20 | 0.3704 | 10 |
| e11 | e11_streamlined_framework | 0.5665 | 0.6590 | 0.8596 | 0.6533 | 0.5000 | 49 | 49 | 26 | 92.0 | 0.6222 | 14 | 0.6780 | 20 | 0.4286 | 15 |
| e12 | e12_general_sink_screening | 0.6199 | 0.7018 | 0.8833 | 0.7067 | 0.5521 | 53 | 43 | 22 | 96.0 | 0.6222 | 14 | 0.6567 | 22 | 0.4928 | 17 |
## Paper-Facing Prompt Refinement Subset

| version | main_change | f1 | dus_f1 | dus_tp | candidate_coverage |
| --- | --- | --- | --- | --- | --- |
| e03 | END candidate review scheme | 0.452 | 0.258 | 8 | 92.0 |
| e09c | Candidate-generation policy including suppression of judgment based only on arguments | 0.564 | 0.381 | 12 | 92.0 |
| e10 | Introduction of the domain adapter into Phase 5 | 0.564 | 0.370 | 10 | 92.0 |
| e11 | Explicit enumeration of shared-memory operations | 0.567 | 0.429 | 15 | 92.0 |
| e12 | Revision of the Phase 3 candidate-screening criteria | 0.620 | 0.493 | 17 | 96.0 |
