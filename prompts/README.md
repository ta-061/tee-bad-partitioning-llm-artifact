# Prompt Experiments

This directory is for controlled prompt experiments.

## Goal
- Keep changes attributable.
- Compare one prompt idea at a time.
- Prefer prompt-design ideas that can be justified by prior prompting literature or by clearly observed failure modes in this project.

## Protocol
1. `e00_*` is the baseline copied from the current best prompt.
2. Each later experiment changes one primary factor only.
3. START/MIDDLE/END should not all change at once unless earlier isolated experiments justify it.
4. Evaluate single-run prompt-renovation first.
5. Only promote a prompt to 5-run actual evaluation if it is competitive with the current baseline.

## Current Tracks
- `e00_v5_1_baseline`
  - Exact baseline track copied from `initial_concept/v5.1`.
- `e01_decomposed_end`
  - Change only END.
  - Hypothesis: decomposed auditing improves category stability without overloading START/MIDDLE.
  - Prompting rationale:
    - decomposition / stepwise reasoning
    - least-to-most style final decision
- `e02_forwarding_gate`
  - Change only END.
  - Hypothesis: many false positives come from forwarding-only call sites; requiring a concrete mechanism at the reviewed line should improve strict precision without rewriting START/MIDDLE.
  - Prompting rationale:
    - failure-driven ablation after `e01`
    - keep candidate-audit structure, but tighten evidence threshold for call-forwarding candidates
- `e03_line_grouped_end`
  - Change END input unit and END prompt together.
  - Hypothesis: same-line competing candidates should be reviewed together, not independently.
  - Prompting rationale:
    - failure-driven redesign after `e01` and `e02`
    - line-level aggregation before final audit
- `e04_udo_tiebreak_line_grouped`
  - Keep line-grouped END, but add an explicit UDO-vs-IVW tie-break for lines that both leak secret data and use attacker-controlled size.
  - Hypothesis: grouped review improves strict/category stability, but UDO recall still suffers unless mixed-mechanism output lines prefer information-leak semantics when the leak is explicit.
  - Prompting rationale:
    - failure-driven refinement after `e03`
    - explicit tie-break for mixed-mechanism same-line candidates
- `e05_line_grouped_boundary_clarification`
  - Keep line-grouped END, but clarify DUS/IVW/UDO boundaries using the concrete failure cases observed in `e03` 5-run consensus.
  - Hypothesis: same-line copies from shared memory into local/private buffers are being over-read as DUS, and shared-derived data is being over-read as UDO; clarifying these boundaries should improve category stability without reintroducing rule-heavy tie-breaks.
  - Prompting rationale:
    - failure analysis after `e03` 5-run consensus
    - boundary clarification instead of category-priority rules
- `e06_line_grouped_v4_priority`
  - Keep line-grouped END, but import only the most useful final-classification logic from `v4`.
  - Hypothesis: `e03` already has a good review unit, but its final category choice is less stable than `v4`; adding `v4`-style promotion gates, priority rules, and contrastive reasoning may recover category precision without returning to sink rediscovery or two-layer output.
  - Prompting rationale:
    - controlled reuse of a historically strong prompt version
    - preserve line-group candidate audit, change only final classification behavior
- `e07_line_grouped_soft_priority`
  - Start from `e03`, but import only the lightweight category-priority part of `v4`, not its stronger promotion gates.
  - Hypothesis: `e06` over-corrected by making final acceptance too strict; keeping `e03` acceptance behavior while restoring only IVW/DUS and UDO/IVW priority may improve category choice without hurting line recall.
  - Prompting rationale:
    - failure-driven ablation after `e06`
    - preserve line-group audit and soft acceptance threshold
- `e08_minimal_end`
  - Drastically reduce END prompt rules. Keep line-group input structure from `e03`, but replace the rule-heavy END with a minimal "role + definitions + output format" structure.
  - Hypothesis: e04–e07 all degraded e03 by adding rules/constraints; the LLM performs better with fewer negative constraints and clearer vulnerability definitions. A modular structure (swappable definitions section) also improves generalizability.
  - Prompting rationale:
    - observation that every rule addition to e03 degraded performance
    - minimal instruction principle: give the task, the definitions, and the output format; let the LLM reason freely
    - modular design: vulnerability definitions are in a clearly delimited section for easy replacement

- `e09a_call_forwarding_fix`
  - Base: `e03`. Change: system.txt only — add CALL-FORWARDING EXCLUSION paragraph.
  - Hypothesis: 10 of 22 e03 FPs are call-forwarding lines; excluding them in system.txt should cut FP by ~10 without affecting TP.
  - Prompting rationale:
    - FP analysis of e03 conversations shows call-forwarding is 45% of all strict FPs
    - minimal change: one paragraph in system.txt, no END changes
- `e09b_call_forwarding_plus_category`
  - Base: `e03`. Change: system.txt (call-forwarding exclusion) + taint_end.txt (IVW/DUS disambiguation hint).
  - Hypothesis: in addition to call-forwarding FP, 4 strict FPs are DUS→IVW category mismatches (lines 208, 212, 227, 290); a one-line hint "when the main risk is unchecked tainted size, prefer IVW over DUS" should fix these.
  - Prompting rationale:
    - addresses both top FP sources: call-forwarding (10 lines) and category mismatch (4 lines)
    - category hint is minimal (2 sentences added to CATEGORY CHECKS)
- `e09c_call_forwarding_plus_recall`
  - Base: `e03`. Change: system.txt (call-forwarding exclusion) + taint_start.txt + taint_middle.txt (candidate generation improvements).
  - Hypothesis: 6 lost TPs (121, 122, 143, 144, 306, 307) were never generated as candidates by START/MIDDLE; explicitly encouraging per-line output candidates for snprintf/memcpy/TEE_MemMove and suppressing call-forwarding candidates should improve recall.
  - Prompting rationale:
    - addresses FP reduction (call-forwarding) and TP improvement (candidate recall) simultaneously
    - START/MIDDLE changes target generation completeness, not category precision
- `e09d_minimal_end_plus_fix`
  - Base: `e08` END + `e03` START/MIDDLE. Change: system.txt (call-forwarding exclusion) + e08 minimal taint_end.txt.
  - Hypothesis: e08's minimal END underperformed partly because call-forwarding FPs overwhelmed it; with call-forwarding suppressed at the system level, e08's simpler END may perform comparably to e03's END.
  - Prompting rationale:
    - re-test the minimal-END concept with the main FP source removed
    - if successful, validates the rule-reduction approach for future generalization
- `e10_modular_framework`
  - Base: `e09c`. Change: all 4 prompt files refactored into domain-agnostic framework + domain configuration file.
  - Hypothesis: e09c's precision can be maintained while making the prompt framework reusable across different vulnerability domains. Domain-specific elements (API names, taint sources, vulnerability categories, sanitizer patterns) are extracted into a separate `domain_optee_bad_partitioning.txt` configuration file with `{placeholder}` notation.
  - Prompting rationale:
    - e09c analysis confirmed 0 benchmark-specific changes; all improvements came from generic taint-analysis principles
    - modular design: swap `domain_*.txt` to target different vulnerability classes (e.g., Android IPC, Linux kernel, web applications)
    - framework prompts use abstract terms (untrusted-visible, trusted-private, OUTPUT SINK API) instead of OP-TEE-specific names
  - Structure:
    - `system.txt`: domain-agnostic framework with `========== DOMAIN-SPECIFIC DEFINITIONS ==========` delimited section
    - `taint_start.txt`: references system prompt's TAINTED SOURCES and OUTPUT SINK APIs instead of hardcoded API names
    - `taint_middle.txt`: same abstraction as taint_start
    - `taint_end.txt`: uses `{placeholder}` for category lists and checks
    - `domain_optee_bad_partitioning.txt`: all OP-TEE specific values (TEE_Param, memref.buffer, TEE_MemMove, UDO/IVW/DUS definitions, etc.)

## Literature Rationale
- Wei et al., 2022. Chain-of-Thought Prompting Elicits Reasoning in Large Language Models.
  - https://arxiv.org/abs/2201.11903
- Zhou et al., 2022. Least-to-Most Prompting Enables Complex Reasoning in Large Language Models.
  - https://arxiv.org/abs/2205.10625
- Wang et al., 2022. Self-Consistency Improves Chain of Thought Reasoning in Language Models.
  - https://arxiv.org/abs/2203.11171

## Notes
- In this project, self-consistency is treated primarily as an evaluation/run strategy, not as a per-prompt output expansion strategy.
- Candidate-audit prompts are expected to preserve the existing backend JSON schema unless the experiment explicitly targets schema changes.
- Generated run results are organized via experiment-name aliases under:
  - `benchmark/partitioningE/bad-partitioning/ta/experiments/gpt-5-mini-2025-08-07/`
  - `bad-partitiont-ta_pronpt_renovation/experiments/gpt-5-mini-2025-08-07/`
- The physical run directories remain `results_N` so that generated JSON files keep their original paths.

## Current Snapshot
- Best experimental result so far: `e09c_call_forwarding_plus_recall`
  - single-run `prompt_renovation`: `Strict F1 0.6800`, `Line F1 0.7200`, `Line-hit category precision 0.9444`
  - 5-run `actual_evaluation`: `Strict F1 0.5772`, `Line F1 0.7114`, `Line-hit category precision 0.8113`
  - interpretation: failure-driven START/MIDDLE modifications (call-forwarding exclusion + per-line output candidate generation) were the most effective improvements; surpassed v4 on Strict F1 and Line F1
- `e10_modular_framework`
  - refactored e09c into domain-agnostic framework; pending evaluation to confirm no regression
- `e11_streamlined_framework`
  - Base: `e10`. Changes: DUS candidate generation strengthening + prompt deduplication + constraint reduction.
  - Hypothesis: e10's DUS recall (0.1935) collapsed because (a) START/MIDDLE lacked explicit per-line DUS candidate generation instructions (unlike the per-line output instructions for snprintf/memcpy), and (b) accumulated redundancy and negative constraints ("Do NOT" rules) consumed context budget and increased run-to-run variance.
  - Changes:
    1. DUS line generation: added "Emit a candidate for EACH line where the trusted side reads/compares/decodes/operates on shared-memory content" to START and MIDDLE (parallel to the existing per-line OUTPUT SINK instruction).
    2. IVW-vs-DUS disambiguation: added "When the primary risk is that the untrusted side can modify the data being read, prefer DUS even if a tainted size is also involved" to DUS definition.
    3. SHARED-MEMORY READ APIS: new domain config section listing strcmp/memcmp/TEE_MemCompare/dec/encrypt/decrypt as shared-read operations.
    4. Deduplication: removed CATEGORY CHECKS from taint_end.txt (was duplicating system.txt definitions); END now references system prompt definitions.
    5. Constraint reduction: merged ~15 "Do NOT" rules into positive instructions; removed SELF-VERIFICATION section (handled by post-processing); removed redundant "No prose" repetitions.
    6. Sanitizer note: merged content_check DUS caveat into SANITIZER PATTERNS inline.
  - Prompting rationale:
    - DUS recall failure analysis from e10 conversations showed model generated 1-2 representative DUS lines per function instead of all lines
    - e09c's per-line output instruction was effective for UDO/IVW; analogous instruction needed for DUS read operations
    - prompt structural analysis showed 43% framework overhead with significant duplication between system.txt and taint_end.txt
    - run-to-run variance (Strict F1 CV=11.4%) partly attributable to high constraint density
