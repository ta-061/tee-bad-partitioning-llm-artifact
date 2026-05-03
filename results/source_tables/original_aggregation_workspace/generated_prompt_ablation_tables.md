# AIES2026 Prompt Ablation Tables

> This note is auto-generated from `bad-partitiont-ta_pronpt_renovation/experiments/*/summary.json`.
> Values are extracted mechanically to avoid manual transcription mistakes.
> Data source: `<ANALYSIS_WORKSPACE>/bad-partitiont-ta_pronpt_renovation/experiments`
> Experiments found: 16

## Table 1: Prompt Ablation Overview (single-run, GPT-5-mini)

| Version | Directory | Strict F1 | Line F1 | CatPrec | UDO F1 | IVW F1 | DUS F1 | DUS TP | Taint F1 | Sanitizer F1 | Delta Strict vs SCIS | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| e00 | e00_v5_1_baseline | 0.3660 | 0.6144 | 0.5957 | 0.2667 | 0.5143 | 0.2000 | 6 | 0.6457 | 0.4000 | -0.0242 | OK |
| e01 | e01_decomposed_end | 0.2857 | 0.5286 | 0.5405 | 0.2500 | 0.3871 | 0.1538 | 4 | 0.6504 | 0.5000 | -0.1045 | OK |
| e02 | e02_forwarding_gate | 0.4027 | 0.5906 | 0.6818 | 0.4324 | 0.4828 | 0.2667 | 8 | 0.6560 | 0.4286 | 0.0124 | OK |
| e03 | e03_line_grouped_end | 0.4521 | 0.5890 | 0.7674 | 0.3636 | 0.5937 | 0.2581 | 8 | 0.6612 | 0.4828 | 0.0618 | OK |
| e04 | e04_udo_tiebreak_line_grouped | 0.4571 | 0.5571 | 0.8205 | 0.5946 | 0.5000 | 0.2456 | 7 | 0.6165 | 0.3750 | 0.0669 | OK |
| e05 | e05_line_grouped_boundary_clarification | 0.3947 | 0.5921 | 0.6667 | 0.2857 | 0.5135 | 0.2373 | 7 | 0.6560 | 0.4828 | 0.0045 | OK |
| e06 | e06_line_grouped_v4_priority | 0.3448 | 0.5517 | 0.6250 | 0.2857 | 0.4478 | 0.1818 | 5 | 0.6308 | 0.4375 | -0.0454 | OK |
| e07 | e07_line_grouped_soft_priority | 0.5600 | 0.5867 | 0.9545 | 0.6667 | 0.6333 | 0.2903 | 9 | 0.6299 | 0.5000 | 0.1698 | OK |
| e08 | e08_minimal_end | 0.5132 | 0.5921 | 0.8667 | 0.5714 | 0.5763 | 0.3279 | 10 | 0.6838 | 0.5000 | 0.1229 | OK |
| e09a | e09a_call_forwarding_fix | 0.3947 | 0.5526 | 0.7143 | 0.4242 | 0.4412 | 0.2623 | 8 | 0.6406 | 0.5000 | 0.0045 | OK |
| e09b | e09b_call_forwarding_plus_category | 0.3867 | 0.5733 | 0.6744 | 0.3889 | 0.4412 | 0.2500 | 7 | 0.6212 | 0.4667 | -0.0036 | OK |
| e09c | e09c_call_forwarding_plus_recall | 0.5644 | 0.6258 | 0.9020 | 0.6222 | 0.6780 | 0.3810 | 12 | 0.7304 | 0.4375 | 0.1742 | OK |
| e09d | e09d_minimal_end_plus_fix | 0.5270 | 0.5946 | 0.8864 | 0.6190 | 0.6129 | 0.2258 | 7 | 0.6667 | 0.4828 | 0.1368 | OK |
| e10 | e10_modular_framework | 0.5641 | 0.6282 | 0.8980 | 0.6222 | 0.6780 | 0.3704 | 10 | 0.5821 | 0.4828 | 0.1739 | OK |
| e11 | e11_streamlined_framework | 0.5665 | 0.6590 | 0.8596 | 0.6222 | 0.6780 | 0.4286 | 15 | 0.5063 | 0.4286 | 0.1762 | OK |
| e12 | e12_general_sink_screening | 0.6199 | 0.7018 | 0.8833 | 0.6222 | 0.6567 | 0.4928 | 17 | 0.4362 | 0.4242 | 0.2296 | OK |

## Table 2: Category Detail (all versions)

| Version | UDO F1 | UDO Prec | UDO Rec | UDO TP | UDO FP | UDO FN | IVW F1 | IVW Prec | IVW Rec | IVW TP | IVW FP | IVW FN | DUS F1 | DUS Prec | DUS Rec | DUS TP | DUS FP | DUS FN |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| e00 | 0.2667 | 0.4444 | 0.1905 | 4 | 5 | 17 | 0.5143 | 0.4286 | 0.6429 | 18 | 24 | 10 | 0.2000 | 0.1765 | 0.2308 | 6 | 28 | 20 |
| e01 | 0.2500 | 0.3636 | 0.1905 | 4 | 7 | 17 | 0.3871 | 0.3529 | 0.4286 | 12 | 22 | 16 | 0.1538 | 0.1538 | 0.1538 | 4 | 22 | 22 |
| e02 | 0.4324 | 0.5000 | 0.3810 | 8 | 8 | 13 | 0.4828 | 0.4667 | 0.5000 | 14 | 16 | 14 | 0.2667 | 0.2353 | 0.3077 | 8 | 26 | 18 |
| e03 | 0.3636 | 0.5000 | 0.2857 | 6 | 6 | 15 | 0.5937 | 0.5278 | 0.6786 | 19 | 17 | 9 | 0.2581 | 0.2222 | 0.3077 | 8 | 28 | 18 |
| e04 | 0.5946 | 0.6875 | 0.5238 | 11 | 5 | 10 | 0.5000 | 0.5000 | 0.5000 | 14 | 14 | 14 | 0.2456 | 0.2258 | 0.2692 | 7 | 24 | 19 |
| e05 | 0.2857 | 0.5714 | 0.1905 | 4 | 3 | 17 | 0.5135 | 0.4130 | 0.6786 | 19 | 27 | 9 | 0.2373 | 0.2121 | 0.2692 | 7 | 26 | 19 |
| e06 | 0.2857 | 0.3571 | 0.2381 | 5 | 9 | 16 | 0.4478 | 0.3846 | 0.5357 | 15 | 24 | 13 | 0.1818 | 0.1724 | 0.1923 | 5 | 24 | 21 |
| e07 | 0.6667 | 0.6667 | 0.6667 | 14 | 7 | 7 | 0.6333 | 0.5938 | 0.6786 | 19 | 13 | 9 | 0.2903 | 0.2500 | 0.3462 | 9 | 27 | 17 |
| e08 | 0.5714 | 0.5714 | 0.5714 | 12 | 9 | 9 | 0.5763 | 0.5484 | 0.6071 | 17 | 14 | 11 | 0.3279 | 0.2857 | 0.3846 | 10 | 25 | 16 |
| e09a | 0.4242 | 0.5833 | 0.3333 | 7 | 5 | 14 | 0.4412 | 0.3750 | 0.5357 | 15 | 25 | 13 | 0.2623 | 0.2286 | 0.3077 | 8 | 27 | 18 |
| e09b | 0.3889 | 0.4667 | 0.3333 | 7 | 8 | 14 | 0.4412 | 0.3750 | 0.5357 | 15 | 25 | 13 | 0.2500 | 0.2333 | 0.2692 | 7 | 23 | 19 |
| e09c | 0.6222 | 0.5833 | 0.6667 | 14 | 10 | 7 | 0.6780 | 0.6452 | 0.7143 | 20 | 11 | 8 | 0.3810 | 0.3243 | 0.4615 | 12 | 25 | 14 |
| e09d | 0.6190 | 0.6190 | 0.6190 | 13 | 8 | 8 | 0.6129 | 0.5588 | 0.6786 | 19 | 15 | 9 | 0.2258 | 0.1944 | 0.2692 | 7 | 29 | 19 |
| e10 | 0.6222 | 0.5833 | 0.6667 | 14 | 10 | 7 | 0.6780 | 0.6452 | 0.7143 | 20 | 11 | 8 | 0.3704 | 0.3571 | 0.3846 | 10 | 18 | 16 |
| e11 | 0.6222 | 0.5833 | 0.6667 | 14 | 10 | 7 | 0.6780 | 0.6452 | 0.7143 | 20 | 11 | 8 | 0.4286 | 0.3409 | 0.5769 | 15 | 29 | 11 |
| e12 | 0.6222 | 0.5833 | 0.6667 | 14 | 10 | 7 | 0.6567 | 0.5641 | 0.7857 | 22 | 17 | 6 | 0.4928 | 0.3953 | 0.6538 | 17 | 26 | 9 |

## Table 3: All Prompt-Renovation Experiments

| Version | Directory | Strict F1 | Line F1 | DUS F1 | DUS TP | Delta Strict | Delta Line | Delta Taint | Delta Sanitizer | Status |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| e00 | e00_v5_1_baseline | 0.3660 | 0.6144 | 0.2000 | 6 | -0.0242 | 0.0453 | 0.0357 | -0.0828 | OK |
| e01 | e01_decomposed_end | 0.2857 | 0.5286 | 0.1538 | 4 | -0.1045 | -0.0405 | 0.0405 | 0.0172 | OK |
| e02 | e02_forwarding_gate | 0.4027 | 0.5906 | 0.2667 | 8 | 0.0124 | 0.0215 | 0.0461 | -0.0542 | OK |
| e03 | e03_line_grouped_end | 0.4521 | 0.5890 | 0.2581 | 8 | 0.0618 | 0.0199 | 0.0512 | 0.0000 | OK |
| e04 | e04_udo_tiebreak_line_grouped | 0.4571 | 0.5571 | 0.2456 | 7 | 0.0669 | -0.0120 | 0.0066 | -0.1078 | OK |
| e05 | e05_line_grouped_boundary_clarification | 0.3947 | 0.5921 | 0.2373 | 7 | 0.0045 | 0.0230 | 0.0461 | 0.0000 | OK |
| e06 | e06_line_grouped_v4_priority | 0.3448 | 0.5517 | 0.1818 | 5 | -0.0454 | -0.0174 | 0.0208 | -0.0453 | OK |
| e07 | e07_line_grouped_soft_priority | 0.5600 | 0.5867 | 0.2903 | 9 | 0.1698 | 0.0176 | 0.0200 | 0.0172 | OK |
| e08 | e08_minimal_end | 0.5132 | 0.5921 | 0.3279 | 10 | 0.1229 | 0.0230 | 0.0738 | 0.0172 | OK |
| e09a | e09a_call_forwarding_fix | 0.3947 | 0.5526 | 0.2623 | 8 | 0.0045 | -0.0165 | 0.0307 | 0.0172 | OK |
| e09b | e09b_call_forwarding_plus_category | 0.3867 | 0.5733 | 0.2500 | 7 | -0.0036 | 0.0042 | 0.0113 | -0.0161 | OK |
| e09c | e09c_call_forwarding_plus_recall | 0.5644 | 0.6258 | 0.3810 | 12 | 0.1742 | 0.0567 | 0.1205 | -0.0453 | OK |
| e09d | e09d_minimal_end_plus_fix | 0.5270 | 0.5946 | 0.2258 | 7 | 0.1368 | 0.0255 | 0.0567 | 0.0000 | OK |
| e10 | e10_modular_framework | 0.5641 | 0.6282 | 0.3704 | 10 | 0.1739 | 0.0591 | -0.0278 | 0.0000 | OK |
| e11 | e11_streamlined_framework | 0.5665 | 0.6590 | 0.4286 | 15 | 0.1762 | 0.0899 | -0.1036 | -0.0542 | OK |
| e12 | e12_general_sink_screening | 0.6199 | 0.7018 | 0.4928 | 17 | 0.2296 | 0.1326 | -0.1738 | -0.0585 | OK |

## Table 4: Chain Coverage (sink / chain / GT line coverage)

| Version | Directory | Mode | Phase3 Profile | Sinks | Chains | GT Lines | Covered | Uncovered | Coverage % | GT Funcs | Covered Funcs | Uncovered Funcs | Uncovered Lines | Uncovered Functions |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| e00 | e00_v5_1_baseline | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e01 | e01_decomposed_end | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e02 | e02_forwarding_gate | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e03 | e03_line_grouped_end | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e04 | e04_udo_tiebreak_line_grouped | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e05 | e05_line_grouped_boundary_clarification | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e06 | e06_line_grouped_v4_priority | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e07 | e07_line_grouped_soft_priority | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e08 | e08_minimal_end | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e09a | e09a_call_forwarding_fix | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e09b | e09b_call_forwarding_plus_category | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e09c | e09c_call_forwarding_plus_recall | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e09d | e09d_minimal_end_plus_fix | llm_only | write-only | 4 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e10 | e10_modular_framework | llm_only | write-only | 5 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e11 | e11_streamlined_framework | llm_only | write-only | 5 | 14 | 75 | 69 | 6 | 92.0 | 12 | 10 | 2 | 254, 256, 258, 319, 326, 329 | produce_i3, produce_s2 |
| e12 | e12_general_sink_screening | llm_only | general | 17 | 26 | 75 | 72 | 3 | 96.0 | 12 | 11 | 1 | 254, 256, 258 | produce_i3 |

## Notes

- All loaded summaries use `--no-group-merge` (`group_merge_pair_mappings = 0`).
