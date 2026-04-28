#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from evaluation_common import (
    Pair,
    apply_group_canonical_map,
    build_group_canonical_pair_map,
    build_consensus_lines,
    build_consensus_pairs,
    build_consensus_sanitizers,
    build_consensus_taints,
    build_taint_sanitizer_eval,
    build_vulnerability_eval,
    delta_verdict,
    evaluate_sanitizer,
    evaluate_taint,
    find_results_dirs,
    line_category_set_metrics,
    line_metrics_from_lines,
    load_ground_truth_pairs,
    load_partial_match_map,
    normalize_category,
    parse_int,
    load_sanitizer_expected,
    load_taint_expected,
    metrics,
    per_category_metrics,
    resolve_conversations_path,
    resolve_vulnerabilities_path,
    summarize_candidate_flow_coverage,
    summarize_pairwise_jaccard,
    summarize_line_jaccard,
    to4,
    write_csv,
)


WORKSPACE_ROOT = Path("/workspace")
DEFAULT_GT = Path("/workspace/bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv")
DEFAULT_PARTIAL = Path("/workspace/bad-partitioning-ta_groundtruth_labels/category_labels/partial_match_lines.csv")
DEFAULT_LABELS = Path("/workspace/bad-partitioning-ta_groundtruth_labels/flow_labels/taint_sanitizer_labels")
DEFAULT_DITING = Path("/workspace/src/metrics/DITING_ans.csv")
DEFAULT_DITING_PROJECTS = "bad-partitioning,badpartitioning"


def _safe_name(path: Path) -> str:
    return path.name or "model"


def _is_model_root_target(path: Path) -> bool:
    if not path.is_dir():
        return False
    return bool(find_results_dirs(path))


def _discover_child_model_roots(root: Path) -> List[Path]:
    targets: List[Path] = []
    if not root.is_dir():
        return targets

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if _is_model_root_target(child):
            targets.append(child)
    return targets


def _metric_block(metric_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tp": metric_dict["tp"],
        "fp": metric_dict["fp"],
        "fn": metric_dict["fn"],
        "pred_count": metric_dict["pred_count"],
        "gt_count": metric_dict["gt_count"],
        "precision": to4(metric_dict["precision"]),
        "recall": to4(metric_dict["recall"]),
        "f1": to4(metric_dict["f1"]),
    }


def _line_metric_block(metric_dict: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "tp": metric_dict["tp"],
        "fp": metric_dict["fp"],
        "fn": metric_dict["fn"],
        "pred_count": metric_dict["pred_count"],
        "gt_count": metric_dict["gt_count"],
        "precision": to4(metric_dict["precision"]),
        "recall": to4(metric_dict["recall"]),
        "f1": to4(metric_dict["f1"]),
    }


def _line_hit_category_precision(strict_metric: Dict[str, Any], line_metric: Dict[str, Any]) -> Dict[str, Any]:
    denominator = line_metric["tp"]
    value = (strict_metric["tp"] / denominator) if denominator > 0 else 0.0
    return {
        "value": to4(value),
        "strict_tp": strict_metric["tp"],
        "line_tp": denominator,
    }


def _category_block(category_metrics: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for category in sorted(category_metrics.keys()):
        out[category] = {
            "tp": category_metrics[category]["tp"],
            "fp": category_metrics[category]["fp"],
            "fn": category_metrics[category]["fn"],
            "precision": to4(category_metrics[category]["precision"]),
            "recall": to4(category_metrics[category]["recall"]),
            "f1": to4(category_metrics[category]["f1"]),
        }
    return out


def _delta_metric_block(current: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "delta_tp": current["tp"] - baseline["tp"],
        "delta_fp": current["fp"] - baseline["fp"],
        "delta_fn": current["fn"] - baseline["fn"],
        "delta_precision": to4(current["precision"] - baseline["precision"]),
        "delta_recall": to4(current["recall"] - baseline["recall"]),
        "delta_f1": to4(current["f1"] - baseline["f1"]),
        "verdict_f1": delta_verdict(current["f1"] - baseline["f1"]),
    }


def _canonical_pairs_from_prediction(
    line: int,
    category: str,
    partial_map: Dict[int, Set[Pair]],
) -> Set[Pair]:
    mapped = partial_map.get(line, set())
    same_category = {pair for pair in mapped if pair.category == category}
    if same_category:
        return same_category
    return {Pair(line, category)}


def _parse_projects(raw: str) -> Set[str]:
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _load_diting_pairs(
    diting_csv: Path,
    projects: Set[str],
    partial_map: Dict[int, Set[Pair]],
) -> Tuple[Set[Pair], Dict[Pair, Dict[str, str]]]:
    pairs: Set[Pair] = set()
    row_meta: Dict[Pair, Dict[str, str]] = {}

    if not diting_csv.exists():
        return pairs, row_meta

    with diting_csv.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            project_raw = (row.get("project") or "").strip().lower()
            if projects and project_raw not in projects:
                continue

            line = (
                parse_int(row.get("start_line"))
                or parse_int(row.get("line"))
                or parse_int(row.get("lineno"))
            )
            category = normalize_category(row.get("category"))
            if line is None or category is None:
                continue

            canonical_pairs = _canonical_pairs_from_prediction(line, category, partial_map)
            for pair in canonical_pairs:
                pairs.add(pair)
                row_meta.setdefault(
                    pair,
                    {
                        "project": row.get("project", ""),
                        "file": row.get("file", ""),
                        "source_line": str(row.get("start_line", "") or row.get("line", "") or ""),
                        "source_category": row.get("category", ""),
                    },
                )

    return pairs, row_meta


def _complementarity_block(
    llm_tp: Set[int],
    diting_tp: Set[int],
    gt_lines: Set[int],
) -> Dict[str, Any]:
    both = llm_tp & diting_tp
    llm_only = llm_tp - diting_tp
    diting_only = diting_tp - llm_tp
    union_tp = llm_tp | diting_tp
    neither = gt_lines - union_tp
    jaccard_den = len(both) + len(llm_only) + len(diting_only)
    return {
        "both_count": len(both),
        "llm_only_count": len(llm_only),
        "diting_only_count": len(diting_only),
        "neither_count": len(neither),
        "gt_count": len(gt_lines),
        "llm_tp_count": len(llm_tp),
        "diting_tp_count": len(diting_tp),
        "union_tp_count": len(union_tp),
        "llm_recall": to4(len(llm_tp) / len(gt_lines) if gt_lines else 0.0),
        "diting_recall": to4(len(diting_tp) / len(gt_lines) if gt_lines else 0.0),
        "union_recall": to4(len(union_tp) / len(gt_lines) if gt_lines else 0.0),
        "union_gain_vs_llm_count": len(union_tp) - len(llm_tp),
        "union_gain_vs_diting_count": len(union_tp) - len(diting_tp),
        "union_gain_vs_llm_recall": to4((len(union_tp) - len(llm_tp)) / len(gt_lines) if gt_lines else 0.0),
        "union_gain_vs_diting_recall": to4((len(union_tp) - len(diting_tp)) / len(gt_lines) if gt_lines else 0.0),
        "tp_overlap_jaccard": to4(len(both) / jaccard_den if jaccard_den else 0.0),
    }


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _coverage_aggregate(items: List[Dict[str, Any]]) -> Dict[str, Any]:
    available_items = [item for item in items if item.get("coverage_available")]
    if not available_items:
        return {
            "run_count_total": len(items),
            "run_count_available": 0,
            "run_count_skipped": len(items),
            "avg_chain_count": 0.0,
            "min_chain_count": 0,
            "max_chain_count": 0,
            "avg_sink_count": 0.0,
            "min_sink_count": 0,
            "max_sink_count": 0,
            "avg_covered_gt_line_count": 0.0,
            "min_covered_gt_line_count": 0,
            "max_covered_gt_line_count": 0,
            "avg_coverage_percent": 0.0,
            "min_coverage_percent": 0.0,
            "max_coverage_percent": 0.0,
        }

    chain_counts = [int(item["chain_count"]) for item in available_items]
    sink_counts = [int(item["sink_count"]) for item in available_items]
    covered_counts = [int(item["covered_gt_line_count"]) for item in available_items]
    coverage_percents = [float(item["coverage_percent"]) for item in available_items]
    return {
        "run_count_total": len(items),
        "run_count_available": len(available_items),
        "run_count_skipped": len(items) - len(available_items),
        "avg_chain_count": to4(_mean([float(v) for v in chain_counts])),
        "min_chain_count": min(chain_counts),
        "max_chain_count": max(chain_counts),
        "avg_sink_count": to4(_mean([float(v) for v in sink_counts])),
        "min_sink_count": min(sink_counts),
        "max_sink_count": max(sink_counts),
        "avg_covered_gt_line_count": to4(_mean([float(v) for v in covered_counts])),
        "min_covered_gt_line_count": min(covered_counts),
        "max_covered_gt_line_count": max(covered_counts),
        "avg_coverage_percent": to4(_mean(coverage_percents)),
        "min_coverage_percent": to4(min(coverage_percents)),
        "max_coverage_percent": to4(max(coverage_percents)),
    }


def _render_coverage_markdown(
    model_root: Path,
    aggregate_all_runs: Dict[str, Any],
    aggregate_consensus_runs: Dict[str, Any],
    coverage_rows: List[Dict[str, Any]],
) -> str:
    lines = [
        f"# Coverage Summary: {model_root.name}",
        "",
        "## Aggregates",
        "",
        (
            f"- All runs: avg chains {aggregate_all_runs['avg_chain_count']:.2f}, "
            f"avg coverage {aggregate_all_runs['avg_covered_gt_line_count']:.2f} GT lines "
            f"({aggregate_all_runs['avg_coverage_percent']:.2f}%), "
            f"available={aggregate_all_runs['run_count_available']}/{aggregate_all_runs['run_count_total']}"
        ),
        (
            f"- Consensus-window runs: avg chains {aggregate_consensus_runs['avg_chain_count']:.2f}, "
            f"avg coverage {aggregate_consensus_runs['avg_covered_gt_line_count']:.2f} GT lines "
            f"({aggregate_consensus_runs['avg_coverage_percent']:.2f}%), "
            f"available={aggregate_consensus_runs['run_count_available']}/{aggregate_consensus_runs['run_count_total']}"
        ),
        "",
        "## Per Run",
        "",
    ]
    for row in coverage_rows:
        if not int(row["coverage_available"]):
            lines.append(
                f"- {row['run_name']}: unavailable ({row['missing_artifacts'] or 'missing coverage artifacts'})"
            )
            continue
        uncovered = row["uncovered_functions"] or "(none)"
        lines.append(
            (
                f"- {row['run_name']}: {row['phase3_profile_inferred']} / "
                f"{row['covered_gt_line_count']}/{row['gt_total_line_count']} "
                f"({float(row['coverage_percent']):.1f}%), "
                f"chains={row['chain_count']}, sinks={row['sink_count']}, "
                f"uncovered={uncovered}"
            )
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate all results_* runs for one model, compute per-run metrics, "
            "and evaluate consensus by majority vote (default: latest 5 runs, >=3 votes)."
        )
    )
    parser.add_argument(
        "model_root_path",
        nargs="?",
        type=Path,
        help="Model root directory containing results_* subdirectories.",
    )
    parser.add_argument(
        "--model-root",
        type=Path,
        default=None,
        help="Model root directory containing results_* subdirectories (same as positional argument).",
    )
    parser.add_argument("--required-runs", type=int, default=5, help="Consensus window size (latest N runs).")
    parser.add_argument("--min-votes", type=int, default=3, help="Minimum votes for consensus inclusion.")
    parser.add_argument("--sanitizer-tolerance", type=int, default=2, help="Line tolerance for optional sanitizer matching.")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GT, help="Ground truth labels CSV.")
    parser.add_argument("--partial-match", type=Path, default=DEFAULT_PARTIAL, help="Partial match mapping CSV.")
    parser.add_argument(
        "--labels-dir",
        type=Path,
        default=None,
        help="Optional taint/sanitizer labels directory. If omitted, only vulnerability and coverage metrics are computed.",
    )
    parser.add_argument(
        "--no-group-merge",
        action="store_true",
        help="Disable canonicalization that merges predictions by manual equivalent GT-line mapping.",
    )
    parser.add_argument("--diting-csv", type=Path, default=DEFAULT_DITING, help="DITING answer CSV path.")
    parser.add_argument(
        "--diting-projects",
        type=str,
        default=DEFAULT_DITING_PROJECTS,
        help="Comma-separated project names to use from DITING CSV.",
    )
    parser.add_argument(
        "--no-diting",
        action="store_true",
        help="Disable DITING complementarity analysis even if DITING CSV exists.",
    )
    parser.add_argument(
        "--with-scis",
        action="store_true",
        help="Also compute SCIS comparison in summary.json (disabled by default for actual evaluation).",
    )
    parser.add_argument(
        "--scis-vuln",
        type=Path,
        default=None,
        help="Optional SCIS baseline vulnerability json for consensus comparison.",
    )
    parser.add_argument(
        "--scis-conversations",
        type=Path,
        default=None,
        help="Optional SCIS baseline conversations jsonl for consensus comparison.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Output directory. Single target: writes directly here. "
            "Batch target: writes one subdirectory per child model root here."
        ),
    )
    args = parser.parse_args()

    model_root = args.model_root or args.model_root_path
    if model_root is None:
        parser.error("model root is required (positional or --model-root).")

    if not model_root.exists():
        raise FileNotFoundError(f"model root not found: {model_root}")
    if not args.ground_truth.exists():
        raise FileNotFoundError(f"ground truth not found: {args.ground_truth}")
    taint_eval_enabled = args.labels_dir is not None
    if taint_eval_enabled and not args.labels_dir.exists():
        raise FileNotFoundError(f"labels dir not found: {args.labels_dir}")

    if not _is_model_root_target(model_root):
        child_targets = _discover_child_model_roots(model_root)
        if not child_targets:
            raise RuntimeError(
                f"No valid results_* directories found under: {model_root} "
                "(and no child model roots containing results_* were found)"
            )

        batch_root = args.output_dir or (WORKSPACE_ROOT / "bad-partitiont-ta_actual_evaluation" / _safe_name(model_root))
        batch_root.mkdir(parents=True, exist_ok=True)

        print(f"[actual_evaluation] batch mode: {len(child_targets)} targets")
        print(f"  input_root  : {model_root}")
        print(f"  output_root : {batch_root}")

        batch_rows: List[Dict[str, Any]] = []
        failures: List[Dict[str, Any]] = []
        script_path = Path(__file__).resolve()

        for target in child_targets:
            child_output = batch_root / _safe_name(target)
            cmd = [
                sys.executable,
                str(script_path),
                str(target),
                "--required-runs",
                str(args.required_runs),
                "--min-votes",
                str(args.min_votes),
                "--ground-truth",
                str(args.ground_truth),
                "--partial-match",
                str(args.partial_match),
                "--diting-csv",
                str(args.diting_csv),
                "--diting-projects",
                str(args.diting_projects),
                "--output-dir",
                str(child_output),
            ]
            if taint_eval_enabled:
                cmd.extend(["--labels-dir", str(args.labels_dir)])
                cmd.extend(["--sanitizer-tolerance", str(args.sanitizer_tolerance)])
            if args.no_group_merge:
                cmd.append("--no-group-merge")
            if args.no_diting:
                cmd.append("--no-diting")
            if args.with_scis:
                cmd.append("--with-scis")
            if args.scis_vuln is not None:
                cmd.extend(["--scis-vuln", str(args.scis_vuln)])
            if args.scis_conversations is not None:
                cmd.extend(["--scis-conversations", str(args.scis_conversations)])

            print(f"\n[batch] evaluating {target.name}")
            result = subprocess.run(cmd)
            row = {
                "target": target.name,
                "input_target": str(target),
                "output_dir": str(child_output),
                "status": "success" if result.returncode == 0 else "failed",
                "return_code": result.returncode,
                "summary_json": str(child_output / "summary.json"),
                "coverage_summary_json": str(child_output / "coverage_summary.json"),
            }
            batch_rows.append(row)
            if result.returncode != 0:
                failures.append(row)

        batch_csv = batch_root / "batch_summary.csv"
        write_csv(
            batch_csv,
            fieldnames=["target", "input_target", "output_dir", "status", "return_code", "summary_json", "coverage_summary_json"],
            rows=batch_rows,
        )
        batch_json = batch_root / "batch_summary.json"
        batch_json.write_text(
            json.dumps(
                {
                    "input_root": str(model_root),
                    "output_root": str(batch_root),
                    "success_count": len(batch_rows) - len(failures),
                    "failure_count": len(failures),
                    "results": batch_rows,
                    "successes": [row for row in batch_rows if row["status"] == "success"],
                    "failures": failures,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        print("\n[actual_evaluation] batch done")
        print(f"  successes    : {len(batch_rows) - len(failures)}")
        print(f"  failures     : {len(failures)}")
        print(f"  batch_csv    : {batch_csv}")
        print(f"  batch_json   : {batch_json}")
        return 0 if not failures else 1

    output_dir = args.output_dir or (WORKSPACE_ROOT / "bad-partitiont-ta_actual_evaluation" / _safe_name(model_root))
    output_dir.mkdir(parents=True, exist_ok=True)

    gt_pairs, gt_meta, gt_line_to_categories = load_ground_truth_pairs(args.ground_truth)
    partial_map = load_partial_match_map(args.partial_match, gt_line_to_categories)
    group_canonical_map = {} if args.no_group_merge else build_group_canonical_pair_map(gt_meta)

    result_dirs = find_results_dirs(model_root)
    if not result_dirs:
        raise RuntimeError(f"No valid results_* directories found under: {model_root}")

    per_run_rows: List[Dict[str, Any]] = []
    run_pred_pairs: List[Set[Pair]] = []
    run_pred_lines_all: List[Set[int]] = []
    run_detected_taints: List[Dict[str, Set[str]]] = []
    run_detected_sanitizers: List[Set[Tuple[str, int]]] = []
    run_labels: List[str] = []
    run_coverages: List[Dict[str, Any]] = []

    for run_index, run_dir in result_dirs:
        vuln_path = resolve_vulnerabilities_path(run_dir)
        try:
            conv_path = resolve_conversations_path(run_dir)
        except FileNotFoundError:
            conv_path = Path("")

        vuln_eval = build_vulnerability_eval(
            vuln_path,
            gt_pairs,
            partial_map=partial_map,
            canonical_pair_map=group_canonical_map,
        )
        ts_eval = None
        if taint_eval_enabled:
            if not conv_path:
                raise FileNotFoundError(f"conversations jsonl not found: {run_dir}")
            ts_eval = build_taint_sanitizer_eval(conv_path, args.labels_dir, sanitizer_tolerance=args.sanitizer_tolerance)

        run_name = run_dir.name
        run_labels.append(run_name)
        run_pred_pairs.append(vuln_eval["pred_pairs"])
        run_pred_lines_all.append(vuln_eval["pred_lines_all"])
        if taint_eval_enabled and ts_eval is not None:
            run_detected_taints.append(ts_eval["detected_taints"])
            run_detected_sanitizers.append(ts_eval["detected_sanitizers"])
        coverage = summarize_candidate_flow_coverage(run_dir, gt_meta)
        run_coverages.append(coverage)

        per_run_row = {
            "run_name": run_name,
            "run_index": run_index,
            "vulnerability_json": str(vuln_path),
            "conversations_jsonl": str(conv_path) if conv_path else "",
            "strict_tp": vuln_eval["strict_metrics"]["tp"],
            "strict_fp": vuln_eval["strict_metrics"]["fp"],
            "strict_fn": vuln_eval["strict_metrics"]["fn"],
            "strict_precision": to4(vuln_eval["strict_metrics"]["precision"]),
            "strict_recall": to4(vuln_eval["strict_metrics"]["recall"]),
            "strict_f1": to4(vuln_eval["strict_metrics"]["f1"]),
            "line_tp": vuln_eval["line_metrics"]["tp"],
            "line_fp": vuln_eval["line_metrics"]["fp"],
            "line_fn": vuln_eval["line_metrics"]["fn"],
            "line_precision": to4(vuln_eval["line_metrics"]["precision"]),
            "line_recall": to4(vuln_eval["line_metrics"]["recall"]),
            "line_f1": to4(vuln_eval["line_metrics"]["f1"]),
            "phase3_profile_inferred": coverage["phase3_profile_inferred"],
            "phase3_profile_source": coverage["phase3_profile_source"],
            "analysis_mode": coverage["analysis_mode"] or "",
            "coverage_available": int(bool(coverage["coverage_available"])),
            "missing_artifacts": ",".join(coverage["missing_artifacts"]),
            "sink_count": coverage["sink_count"],
            "chain_count": coverage["chain_count"],
            "covered_gt_line_count": coverage["covered_gt_line_count"],
            "gt_total_line_count": coverage["gt_total_line_count"],
            "coverage_percent": coverage["coverage_percent"],
            "uncovered_functions": ",".join(coverage["uncovered_functions"]),
        }
        if taint_eval_enabled and ts_eval is not None:
            per_run_row.update(
                {
                    "taint_tp": ts_eval["taint_metrics"]["tp"],
                    "taint_fp": ts_eval["taint_metrics"]["fp"],
                    "taint_fn": ts_eval["taint_metrics"]["fn"],
                    "taint_precision": to4(ts_eval["taint_metrics"]["precision"]),
                    "taint_recall": to4(ts_eval["taint_metrics"]["recall"]),
                    "taint_f1": to4(ts_eval["taint_metrics"]["f1"]),
                    "sanitizer_tp": ts_eval["sanitizer_metrics"]["tp"],
                    "sanitizer_fp": ts_eval["sanitizer_metrics"]["fp"],
                    "sanitizer_fn": ts_eval["sanitizer_metrics"]["fn"],
                    "sanitizer_precision": to4(ts_eval["sanitizer_metrics"]["precision"]),
                    "sanitizer_recall": to4(ts_eval["sanitizer_metrics"]["recall"]),
                    "sanitizer_f1": to4(ts_eval["sanitizer_metrics"]["f1"]),
                }
            )
        per_run_rows.append(per_run_row)

    per_run_csv = output_dir / "per_run_metrics.csv"
    write_csv(
        per_run_csv,
        fieldnames=[
            "run_name",
            "run_index",
            "vulnerability_json",
            "conversations_jsonl",
            "strict_tp",
            "strict_fp",
            "strict_fn",
            "strict_precision",
            "strict_recall",
            "strict_f1",
            "line_tp",
            "line_fp",
            "line_fn",
            "line_precision",
            "line_recall",
            "line_f1",
            "phase3_profile_inferred",
            "phase3_profile_source",
            "analysis_mode",
            "coverage_available",
            "missing_artifacts",
            "sink_count",
            "chain_count",
            "covered_gt_line_count",
            "gt_total_line_count",
            "coverage_percent",
            "uncovered_functions",
        ]
        + (
            [
                "taint_tp",
                "taint_fp",
                "taint_fn",
                "taint_precision",
                "taint_recall",
                "taint_f1",
                "sanitizer_tp",
                "sanitizer_fp",
                "sanitizer_fn",
                "sanitizer_precision",
                "sanitizer_recall",
                "sanitizer_f1",
            ]
            if taint_eval_enabled
            else []
        ),
        rows=per_run_rows,
    )

    coverage_rows: List[Dict[str, Any]] = []
    for row, coverage in zip(per_run_rows, run_coverages):
        coverage_rows.append(
            {
                "run_name": row["run_name"],
                "run_index": row["run_index"],
                "results_dir": coverage["results_dir"],
                "phase3_profile_inferred": coverage["phase3_profile_inferred"],
                "phase3_profile_source": coverage["phase3_profile_source"],
                "analysis_mode": coverage["analysis_mode"] or "",
                "coverage_available": int(bool(coverage["coverage_available"])),
                "missing_artifacts": ",".join(coverage["missing_artifacts"]),
                "sink_count": coverage["sink_count"],
                "chain_count": coverage["chain_count"],
                "covered_gt_line_count": coverage["covered_gt_line_count"],
                "gt_total_line_count": coverage["gt_total_line_count"],
                "uncovered_gt_line_count": coverage["uncovered_gt_line_count"],
                "coverage_percent": coverage["coverage_percent"],
                "uncovered_functions": ",".join(coverage["uncovered_functions"]),
                "uncovered_gt_lines": ",".join(str(line) for line in coverage["uncovered_gt_lines"]),
            }
        )

    coverage_csv = output_dir / "coverage_per_run.csv"
    write_csv(
        coverage_csv,
        fieldnames=[
            "run_name",
            "run_index",
            "results_dir",
            "phase3_profile_inferred",
            "phase3_profile_source",
            "analysis_mode",
            "coverage_available",
            "missing_artifacts",
            "sink_count",
            "chain_count",
            "covered_gt_line_count",
            "gt_total_line_count",
            "uncovered_gt_line_count",
            "coverage_percent",
            "uncovered_functions",
            "uncovered_gt_lines",
        ],
        rows=coverage_rows,
    )

    total_runs = len(result_dirs)
    consensus_window = min(args.required_runs, total_runs)
    selected_indices = list(range(total_runs - consensus_window, total_runs))
    selected_pairs = [run_pred_pairs[i] for i in selected_indices]
    selected_lines = [run_pred_lines_all[i] for i in selected_indices]
    selected_taints = [run_detected_taints[i] for i in selected_indices] if taint_eval_enabled else []
    selected_sanitizers = [run_detected_sanitizers[i] for i in selected_indices] if taint_eval_enabled else []
    selected_names = [run_labels[i] for i in selected_indices]
    selected_per_run_rows = [per_run_rows[i] for i in selected_indices]
    selected_coverages = [run_coverages[i] for i in selected_indices]

    effective_min_votes = min(args.min_votes, consensus_window)
    consensus_pairs, pair_votes = build_consensus_pairs(selected_pairs, min_votes=effective_min_votes)
    consensus_lines, _line_votes = build_consensus_lines(selected_lines, min_votes=effective_min_votes)
    consensus_pair_metrics = metrics(consensus_pairs, gt_pairs)
    consensus_strict_metrics = line_metrics_from_lines(consensus_lines, gt_pairs)
    # strict line+category-set: a line is TP iff predicted categories on that line intersect GT categories.
    line_to_pred_categories: Dict[int, Set[str]] = {}
    for pair in consensus_pairs:
        line_to_pred_categories.setdefault(pair.line, set()).add(pair.category)
    strict_tp_set: Set[int] = set()
    strict_fp_set: Set[int] = set()
    gt_line_to_categories = {pair.line: set() for pair in gt_pairs}
    for pair in gt_pairs:
        gt_line_to_categories[pair.line].add(pair.category)
    for line in consensus_lines:
        pred_cats = line_to_pred_categories.get(line, set())
        gt_cats = gt_line_to_categories.get(line, set())
        if line in gt_line_to_categories and (pred_cats & gt_cats):
            strict_tp_set.add(line)
        else:
            strict_fp_set.add(line)
    strict_fn_set: Set[int] = set()
    for line, gt_cats in gt_line_to_categories.items():
        pred_cats = line_to_pred_categories.get(line, set())
        if not (line in consensus_lines and (pred_cats & gt_cats)):
            strict_fn_set.add(line)
    strict_precision = len(strict_tp_set) / len(consensus_lines) if consensus_lines else 0.0
    strict_recall = len(strict_tp_set) / len(gt_line_to_categories) if gt_line_to_categories else 0.0
    strict_f1 = (2 * strict_precision * strict_recall / (strict_precision + strict_recall)) if (strict_precision + strict_recall) > 0 else 0.0
    consensus_strict_metrics = {
        "tp_set": strict_tp_set,
        "fp_set": strict_fp_set,
        "fn_set": strict_fn_set,
        "tp": len(strict_tp_set),
        "fp": len(strict_fp_set),
        "fn": len(strict_fn_set),
        "pred_count": len(consensus_lines),
        "gt_count": len(gt_line_to_categories),
        "precision": strict_precision,
        "recall": strict_recall,
        "f1": strict_f1,
    }
    consensus_line_metrics = line_metrics_from_lines(consensus_lines, gt_pairs)
    consensus_category_metrics = per_category_metrics(consensus_pairs, gt_pairs)

    consensus_taint_metrics = None
    consensus_sanitizer_metrics = None
    if taint_eval_enabled:
        expected_taints = load_taint_expected(args.labels_dir)
        expected_sanitizers = load_sanitizer_expected(args.labels_dir)
        consensus_detected_taints = build_consensus_taints(selected_taints, min_votes=effective_min_votes)
        consensus_detected_sanitizers = build_consensus_sanitizers(selected_sanitizers, min_votes=effective_min_votes)
        consensus_taint_metrics = evaluate_taint(expected_taints, consensus_detected_taints)
        consensus_sanitizer_metrics = evaluate_sanitizer(
            expected_sanitizers,
            consensus_detected_sanitizers,
            tolerance=args.sanitizer_tolerance,
        )

    strict_f1_values = [float(row["strict_f1"]) for row in selected_per_run_rows]
    run_stability = {
        "strict_f1": {
            "min": to4(min(strict_f1_values)) if strict_f1_values else 0.0,
            "max": to4(max(strict_f1_values)) if strict_f1_values else 0.0,
            "range": to4(max(strict_f1_values) - min(strict_f1_values)) if strict_f1_values else 0.0,
        },
        "strict_jaccard": summarize_pairwise_jaccard(selected_pairs),
        "line_only_jaccard": summarize_line_jaccard(selected_lines),
    }

    gt_lines_by_function: Dict[str, Set[int]] = defaultdict(set)
    for pair, meta in gt_meta.items():
        function_name = meta.get("function", "")
        if function_name:
            gt_lines_by_function[function_name].add(pair.line)

    def _uncovered_frequency(items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        counts: Dict[str, int] = defaultdict(int)
        available_items = [item for item in items if item.get("coverage_available")]
        for item in available_items:
            for function_name in item["uncovered_functions"]:
                counts[function_name] += 1
        rows: List[Dict[str, Any]] = []
        run_count = len(available_items)
        for function_name in sorted(gt_lines_by_function.keys()):
            missing = counts.get(function_name, 0)
            rows.append(
                {
                    "function": function_name,
                    "gt_line_count": len(gt_lines_by_function[function_name]),
                    "runs_missing": missing,
                    "runs_covering": run_count - missing,
                    "missing_ratio": to4(missing / run_count if run_count else 0.0),
                }
            )
        return rows

    coverage_aggregate_all_runs = _coverage_aggregate(run_coverages)
    coverage_aggregate_consensus_runs = _coverage_aggregate(selected_coverages)
    uncovered_frequency_all_runs = _uncovered_frequency(run_coverages)
    uncovered_frequency_consensus_runs = _uncovered_frequency(selected_coverages)

    uncovered_frequency_csv = output_dir / "uncovered_function_frequency.csv"
    write_csv(
        uncovered_frequency_csv,
        fieldnames=["function", "gt_line_count", "runs_missing", "runs_covering", "missing_ratio"],
        rows=uncovered_frequency_all_runs,
    )

    # DITING complementarity analysis
    diting_enabled = (not args.no_diting) and args.diting_csv.exists()
    diting_rows_written: Dict[str, str] = {}
    diting_complementarity: Dict[str, Any] = {"enabled": False}
    if diting_enabled:
        diting_projects = _parse_projects(args.diting_projects)
        diting_pairs, diting_row_meta = _load_diting_pairs(args.diting_csv, diting_projects, partial_map)
        diting_pairs, diting_lines = apply_group_canonical_map(
            diting_pairs,
            {pair.line for pair in diting_pairs},
            group_canonical_map,
        )
        if group_canonical_map:
            remapped_meta: Dict[Pair, Dict[str, str]] = {}
            for pair, meta in diting_row_meta.items():
                remapped_meta.setdefault(group_canonical_map.get(pair, pair), meta)
            diting_row_meta = remapped_meta
        diting_pair_metrics = metrics(diting_pairs, gt_pairs)
        diting_line_metrics = line_metrics_from_lines(diting_lines, gt_pairs)
        diting_strict_metrics = line_category_set_metrics(diting_lines, diting_pairs, gt_line_to_categories)

        combined_pairs = consensus_pairs | diting_pairs
        combined_lines = consensus_lines | diting_lines
        combined_pair_metrics = metrics(combined_pairs, gt_pairs)
        combined_line_metrics = line_metrics_from_lines(combined_lines, gt_pairs)
        combined_strict_metrics = line_category_set_metrics(combined_lines, combined_pairs, gt_line_to_categories)

        gt_lines = set(gt_line_to_categories.keys())
        strict_comp = _complementarity_block(
            consensus_strict_metrics["tp_set"],
            diting_strict_metrics["tp_set"],
            gt_lines,
        )
        line_comp = _complementarity_block(
            consensus_line_metrics["tp_set"],
            diting_line_metrics["tp_set"],
            gt_lines,
        )

        pair_breakdown_rows: List[Dict[str, Any]] = []
        for pair in sorted(gt_pairs):
            llm_strict_hit = pair.line in consensus_strict_metrics["tp_set"]
            diting_strict_hit = pair.line in diting_strict_metrics["tp_set"]
            llm_line_hit = pair.line in consensus_line_metrics["tp_set"]
            diting_line_hit = pair.line in diting_line_metrics["tp_set"]
            strict_bucket = (
                "both"
                if llm_strict_hit and diting_strict_hit
                else ("llm_only" if llm_strict_hit else ("diting_only" if diting_strict_hit else "neither"))
            )
            line_bucket = (
                "both"
                if llm_line_hit and diting_line_hit
                else ("llm_only" if llm_line_hit else ("diting_only" if diting_line_hit else "neither"))
            )
            meta = gt_meta.get(pair, {})
            pair_breakdown_rows.append(
                {
                    "line": pair.line,
                    "category": pair.category,
                    "function": meta.get("function", ""),
                    "label_id": meta.get("label_id", ""),
                    "group": meta.get("group", ""),
                    "llm_strict_hit": int(llm_strict_hit),
                    "diting_strict_hit": int(diting_strict_hit),
                    "llm_line_hit": int(llm_line_hit),
                    "diting_line_hit": int(diting_line_hit),
                    "strict_bucket": strict_bucket,
                    "line_bucket": line_bucket,
                }
            )

        pair_breakdown_csv = output_dir / "diting_llm_gt_pair_breakdown.csv"
        write_csv(
            pair_breakdown_csv,
            fieldnames=[
                "line",
                "category",
                "function",
                "label_id",
                "group",
                "llm_strict_hit",
                "diting_strict_hit",
                "llm_line_hit",
                "diting_line_hit",
                "strict_bucket",
                "line_bucket",
            ],
            rows=pair_breakdown_rows,
        )

        # Bucket characteristics by category/function/group
        bucket_stats: Dict[Tuple[str, str, str, str], int] = defaultdict(int)
        bucket_totals: Dict[Tuple[str, str], int] = defaultdict(int)
        for row in pair_breakdown_rows:
            for scope, bucket_key in (("strict", "strict_bucket"), ("line", "line_bucket")):
                bucket = row[bucket_key]
                bucket_totals[(scope, bucket)] += 1
                for metric, key in (
                    ("category", row["category"]),
                    ("function", row["function"]),
                    ("group", row["group"]),
                ):
                    bucket_stats[(scope, metric, bucket, str(key))] += 1

        characteristics_rows: List[Dict[str, Any]] = []
        for (scope, metric, bucket, key), count in sorted(bucket_stats.items()):
            total = bucket_totals[(scope, bucket)]
            characteristics_rows.append(
                {
                    "scope": scope,
                    "metric": metric,
                    "bucket": bucket,
                    "key": key,
                    "count": count,
                    "bucket_total": total,
                    "ratio_in_bucket": to4(count / total if total else 0.0),
                }
            )

        characteristics_csv = output_dir / "diting_llm_bucket_characteristics.csv"
        write_csv(
            characteristics_csv,
            fieldnames=["scope", "metric", "bucket", "key", "count", "bucket_total", "ratio_in_bucket"],
            rows=characteristics_rows,
        )

        # Prediction overlap (includes FP/FN inspection, not only GT rows)
        pred_overlap_rows: List[Dict[str, Any]] = []
        pred_universe = set(consensus_pairs) | set(diting_pairs) | set(gt_pairs)
        for pair in sorted(pred_universe):
            in_llm = pair in consensus_pairs
            in_diting = pair in diting_pairs
            in_gt = pair in gt_pairs
            if in_llm and in_diting:
                overlap_bucket = "both"
            elif in_llm:
                overlap_bucket = "llm_only"
            elif in_diting:
                overlap_bucket = "diting_only"
            else:
                overlap_bucket = "neither"

            if in_gt and in_llm and in_diting:
                status = "tp_both"
            elif in_gt and in_llm and not in_diting:
                status = "tp_llm_only"
            elif in_gt and in_diting and not in_llm:
                status = "tp_diting_only"
            elif in_gt and (not in_llm) and (not in_diting):
                status = "fn_both"
            elif (not in_gt) and in_llm and in_diting:
                status = "fp_both"
            elif (not in_gt) and in_llm and (not in_diting):
                status = "fp_llm_only"
            elif (not in_gt) and in_diting and (not in_llm):
                status = "fp_diting_only"
            else:
                status = "none"

            meta = gt_meta.get(pair, {})
            diting_meta = diting_row_meta.get(pair, {})
            pred_overlap_rows.append(
                {
                    "line": pair.line,
                    "category": pair.category,
                    "in_llm": int(in_llm),
                    "in_diting": int(in_diting),
                    "is_ground_truth": int(in_gt),
                    "overlap_bucket": overlap_bucket,
                    "status": status,
                    "function": meta.get("function", ""),
                    "label_id": meta.get("label_id", ""),
                    "group": meta.get("group", ""),
                    "diting_project": diting_meta.get("project", ""),
                    "diting_file": diting_meta.get("file", ""),
                    "diting_source_line": diting_meta.get("source_line", ""),
                    "diting_source_category": diting_meta.get("source_category", ""),
                }
            )

        pred_overlap_csv = output_dir / "diting_llm_prediction_overlap.csv"
        write_csv(
            pred_overlap_csv,
            fieldnames=[
                "line",
                "category",
                "in_llm",
                "in_diting",
                "is_ground_truth",
                "overlap_bucket",
                "status",
                "function",
                "label_id",
                "group",
                "diting_project",
                "diting_file",
                "diting_source_line",
                "diting_source_category",
            ],
            rows=pred_overlap_rows,
        )

        diting_rows_written = {
            "gt_pair_breakdown_csv": str(pair_breakdown_csv),
            "bucket_characteristics_csv": str(characteristics_csv),
            "prediction_overlap_csv": str(pred_overlap_csv),
        }

        diting_complementarity = {
            "enabled": True,
            "source": {
                "diting_csv": str(args.diting_csv),
                "projects": sorted(diting_projects),
            },
            "scoring_policy": {
                "strict_line_category": "line+category-set overlap match (same as target strict metric)",
                "line_only": "line localization match (category ignored)",
            },
            "llm_only": {
                "strict_line_category": _metric_block(consensus_strict_metrics),
                "line_only": _line_metric_block(consensus_line_metrics),
                "pair": _metric_block(consensus_pair_metrics),
            },
            "diting_only": {
                "strict_line_category": _metric_block(diting_strict_metrics),
                "line_only": _line_metric_block(diting_line_metrics),
                "pair": _metric_block(diting_pair_metrics),
            },
            "combined_union": {
                "strict_line_category": _metric_block(combined_strict_metrics),
                "line_only": _line_metric_block(combined_line_metrics),
                "pair": _metric_block(combined_pair_metrics),
                "delta_vs_llm": {
                    "strict_tp": combined_strict_metrics["tp"] - consensus_strict_metrics["tp"],
                    "strict_recall": to4(combined_strict_metrics["recall"] - consensus_strict_metrics["recall"]),
                    "strict_f1": to4(combined_strict_metrics["f1"] - consensus_strict_metrics["f1"]),
                    "line_tp": combined_line_metrics["tp"] - consensus_line_metrics["tp"],
                    "line_recall": to4(combined_line_metrics["recall"] - consensus_line_metrics["recall"]),
                    "line_f1": to4(combined_line_metrics["f1"] - consensus_line_metrics["f1"]),
                },
                "delta_vs_diting": {
                    "strict_tp": combined_strict_metrics["tp"] - diting_strict_metrics["tp"],
                    "strict_recall": to4(combined_strict_metrics["recall"] - diting_strict_metrics["recall"]),
                    "strict_f1": to4(combined_strict_metrics["f1"] - diting_strict_metrics["f1"]),
                    "line_tp": combined_line_metrics["tp"] - diting_line_metrics["tp"],
                    "line_recall": to4(combined_line_metrics["recall"] - diting_line_metrics["recall"]),
                    "line_f1": to4(combined_line_metrics["f1"] - diting_line_metrics["f1"]),
                },
            },
            "overlap_on_ground_truth": {
                "strict_line_category": strict_comp,
                "line_only": line_comp,
            },
            "outputs": diting_rows_written,
        }

    vote_rows: List[Dict[str, Any]] = []
    vote_universe = set(pair_votes.keys()) | gt_pairs
    for pair in sorted(vote_universe):
        votes = pair_votes.get(pair, 0)
        in_consensus = pair in consensus_pairs
        in_gt = pair in gt_pairs
        if in_consensus and in_gt:
            status = "TP"
        elif in_consensus and not in_gt:
            status = "FP"
        elif (not in_consensus) and in_gt:
            status = "FN"
        else:
            status = "none"
        meta = gt_meta.get(pair, {})
        vote_rows.append(
            {
                "line": pair.line,
                "category": pair.category,
                "votes": votes,
                "in_consensus": int(in_consensus),
                "is_ground_truth": int(in_gt),
                "status": status,
                "function": meta.get("function", ""),
                "label_id": meta.get("label_id", ""),
                "group": meta.get("group", ""),
            }
        )

    votes_csv = output_dir / "consensus_pair_votes.csv"
    write_csv(
        votes_csv,
        fieldnames=[
            "line",
            "category",
            "votes",
            "in_consensus",
            "is_ground_truth",
            "status",
            "function",
            "label_id",
            "group",
        ],
        rows=vote_rows,
    )

    gt_consensus_rows: List[Dict[str, Any]] = []
    for pair in sorted(gt_pairs):
        in_consensus = pair.line in consensus_strict_metrics["tp_set"]
        gt_meta_row = gt_meta.get(pair, {})
        gt_consensus_rows.append(
            {
                "line": pair.line,
                "category": pair.category,
                "function": gt_meta_row.get("function", ""),
                "label_id": gt_meta_row.get("label_id", ""),
                "group": gt_meta_row.get("group", ""),
                "votes": pair_votes.get(pair, 0),
                "consensus_hit": int(in_consensus),
            }
        )
    gt_consensus_csv = output_dir / "ground_truth_consensus_hits.csv"
    write_csv(
        gt_consensus_csv,
        fieldnames=["line", "category", "function", "label_id", "group", "votes", "consensus_hit"],
        rows=gt_consensus_rows,
    )

    category_rows: List[Dict[str, Any]] = []
    for category in sorted(consensus_category_metrics.keys()):
        item = consensus_category_metrics[category]
        category_rows.append(
            {
                "scope": "category_pair",
                "category": category,
                "tp": item["tp"],
                "fp": item["fp"],
                "fn": item["fn"],
                "precision": to4(item["precision"]),
                "recall": to4(item["recall"]),
                "f1": to4(item["f1"]),
            }
        )
    category_rows.append(
        {
            "scope": "overall_strict_line_category",
            "category": "all",
            "tp": consensus_strict_metrics["tp"],
            "fp": consensus_strict_metrics["fp"],
            "fn": consensus_strict_metrics["fn"],
            "precision": to4(consensus_strict_metrics["precision"]),
            "recall": to4(consensus_strict_metrics["recall"]),
            "f1": to4(consensus_strict_metrics["f1"]),
        }
    )
    category_rows.append(
        {
            "scope": "overall_line",
            "category": "all",
            "tp": consensus_line_metrics["tp"],
            "fp": consensus_line_metrics["fp"],
            "fn": consensus_line_metrics["fn"],
            "precision": to4(consensus_line_metrics["precision"]),
            "recall": to4(consensus_line_metrics["recall"]),
            "f1": to4(consensus_line_metrics["f1"]),
        }
    )
    category_csv = output_dir / "consensus_category_metrics.csv"
    write_csv(
        category_csv,
        fieldnames=["scope", "category", "tp", "fp", "fn", "precision", "recall", "f1"],
        rows=category_rows,
    )

    target_scores = {
        "vulnerability_all": {
            "strict_line_category": _metric_block(consensus_strict_metrics),
            "line_only": _line_metric_block(consensus_line_metrics),
            "line_hit_category_precision": _line_hit_category_precision(consensus_strict_metrics, consensus_line_metrics),
        },
        "vulnerability_by_category": _category_block(consensus_category_metrics),
    }
    if taint_eval_enabled and consensus_taint_metrics is not None and consensus_sanitizer_metrics is not None:
        target_scores.update(
            {
                "taint_propagation": {
                    "tp": consensus_taint_metrics["tp"],
                    "fp": consensus_taint_metrics["fp"],
                    "fn": consensus_taint_metrics["fn"],
                    "expected_count": consensus_taint_metrics["expected_count"],
                    "precision": to4(consensus_taint_metrics["precision"]),
                    "recall": to4(consensus_taint_metrics["recall"]),
                    "f1": to4(consensus_taint_metrics["f1"]),
                },
                "sanitizer_recognition": {
                    "tp": consensus_sanitizer_metrics["tp"],
                    "fp": consensus_sanitizer_metrics["fp"],
                    "fn": consensus_sanitizer_metrics["fn"],
                    "expected_count": consensus_sanitizer_metrics["expected_count"],
                    "precision": to4(consensus_sanitizer_metrics["precision"]),
                    "recall": to4(consensus_sanitizer_metrics["recall"]),
                    "f1": to4(consensus_sanitizer_metrics["f1"]),
                },
            }
        )

    diff_vs_scis: Dict[str, Any] = {"enabled": False}
    scis_scores: Dict[str, Any] = {}
    if args.with_scis:
        if args.scis_vuln is None or args.scis_conversations is None:
            raise ValueError("--with-scis requires both --scis-vuln and --scis-conversations")
        if not args.scis_vuln.exists() or not args.scis_conversations.exists():
            raise FileNotFoundError("SCIS files not found. Check --scis-vuln / --scis-conversations.")

        scis_v = build_vulnerability_eval(
            args.scis_vuln,
            gt_pairs,
            partial_map=partial_map,
            canonical_pair_map=group_canonical_map,
        )
        scis_scores = {
            "source": {
                "vulnerability_json": str(args.scis_vuln),
                "conversations_jsonl": str(args.scis_conversations),
            },
            "vulnerability_all": {
                "strict_line_category": _metric_block(scis_v["strict_metrics"]),
                "line_only": _line_metric_block(scis_v["line_metrics"]),
                "line_hit_category_precision": _line_hit_category_precision(scis_v["strict_metrics"], scis_v["line_metrics"]),
            },
            "vulnerability_by_category": _category_block(scis_v["category_metrics"]),
        }
        if taint_eval_enabled:
            scis_ts = build_taint_sanitizer_eval(
                args.scis_conversations,
                args.labels_dir,
                sanitizer_tolerance=args.sanitizer_tolerance,
            )
            scis_scores.update(
                {
                    "taint_propagation": {
                        "tp": scis_ts["taint_metrics"]["tp"],
                        "fp": scis_ts["taint_metrics"]["fp"],
                        "fn": scis_ts["taint_metrics"]["fn"],
                        "expected_count": scis_ts["taint_metrics"]["expected_count"],
                        "precision": to4(scis_ts["taint_metrics"]["precision"]),
                        "recall": to4(scis_ts["taint_metrics"]["recall"]),
                        "f1": to4(scis_ts["taint_metrics"]["f1"]),
                    },
                    "sanitizer_recognition": {
                        "tp": scis_ts["sanitizer_metrics"]["tp"],
                        "fp": scis_ts["sanitizer_metrics"]["fp"],
                        "fn": scis_ts["sanitizer_metrics"]["fn"],
                        "expected_count": scis_ts["sanitizer_metrics"]["expected_count"],
                        "precision": to4(scis_ts["sanitizer_metrics"]["precision"]),
                        "recall": to4(scis_ts["sanitizer_metrics"]["recall"]),
                        "f1": to4(scis_ts["sanitizer_metrics"]["f1"]),
                    },
                }
            )

        category_delta: Dict[str, Dict[str, Any]] = {}
        target_cat = target_scores["vulnerability_by_category"]
        scis_cat = scis_scores["vulnerability_by_category"]
        for category in sorted(target_cat.keys()):
            category_delta[category] = _delta_metric_block(target_cat[category], scis_cat[category])

        scis_pred_lines = set(scis_v["pred_lines_all"])
        scis_missed_line_hit = sorted(
            [
                {"line": pair.line, "category": pair.category}
                for pair in gt_pairs
                if pair.line not in scis_v["strict_metrics"]["tp_set"] and pair.line in scis_pred_lines
            ],
            key=lambda x: (x["line"], x["category"]),
        )

        diff_vs_scis = {
            "enabled": True,
            "vulnerability_all": {
                "strict_line_category": _delta_metric_block(
                    target_scores["vulnerability_all"]["strict_line_category"],
                    scis_scores["vulnerability_all"]["strict_line_category"],
                ),
                "line_only": _delta_metric_block(
                    target_scores["vulnerability_all"]["line_only"],
                    scis_scores["vulnerability_all"]["line_only"],
                ),
            },
            "vulnerability_by_category": category_delta,
            "diagnostics": {
                "scis_strict_tp_observed": scis_scores["vulnerability_all"]["strict_line_category"]["tp"],
                "scis_strict_fp_observed": scis_scores["vulnerability_all"]["strict_line_category"]["fp"],
                "scis_strict_fn_observed": scis_scores["vulnerability_all"]["strict_line_category"]["fn"],
                "ground_truth_pairs_missed_but_line_detected_count": len(scis_missed_line_hit),
                "ground_truth_pairs_missed_but_line_detected": scis_missed_line_hit,
            },
        }
        if taint_eval_enabled:
            diff_vs_scis.update(
                {
                    "taint_propagation": _delta_metric_block(
                        target_scores["taint_propagation"],
                        scis_scores["taint_propagation"],
                    ),
                    "sanitizer_recognition": _delta_metric_block(
                        target_scores["sanitizer_recognition"],
                        scis_scores["sanitizer_recognition"],
                    ),
                }
            )

    summary = {
        "model_root": str(model_root),
        "output_dir": str(output_dir),
        "config": {
            "required_runs": args.required_runs,
            "min_votes": args.min_votes,
            "effective_consensus_window": consensus_window,
            "effective_min_votes": effective_min_votes,
            "ground_truth": str(args.ground_truth),
            "partial_match": str(args.partial_match),
            "group_merge_enabled": not args.no_group_merge,
            "group_merge_pair_mappings": len(group_canonical_map),
            "taint_sanitizer_eval_enabled": taint_eval_enabled,
            "diting_csv": str(args.diting_csv),
            "diting_projects": args.diting_projects,
            "diting_enabled": diting_enabled,
        },
        "runs": {
            "total_found": total_runs,
            "all_runs": run_labels,
            "runs_used_for_consensus": selected_names,
        },
        "run_stability": run_stability,
        "coverage": {
            "schema_version": 1,
            "coverage_mode": "multi_run_consensus",
            "coverage_basis": (
                "function_chain_proxy: if a ground-truth function appears in any "
                "candidate flow chain, all GT lines for that function are counted as covered"
            ),
            "per_run_csv": str(coverage_csv),
            "results": coverage_rows,
            "per_run": coverage_rows,
            "uncovered_function_frequency_csv": str(uncovered_frequency_csv),
            "aggregate_all_runs": coverage_aggregate_all_runs,
            "aggregate_selected_runs": coverage_aggregate_consensus_runs,
            "aggregate_consensus_runs": coverage_aggregate_consensus_runs,
            "latest_run": run_coverages[-1] if run_coverages else None,
            "uncovered_function_frequency_all_runs": uncovered_frequency_all_runs,
            "uncovered_function_frequency_selected_runs": uncovered_frequency_consensus_runs,
            "uncovered_function_frequency_consensus_runs": uncovered_frequency_consensus_runs,
        },
        "scoring_policy": {
            "pair_scoring": "line+category-set overlap match",
            "line_scoring": "line-only localization match over all detected lines (category ignored; includes other)",
            "line_hit_category_precision": "strict_tp / line_tp",
            "partial_match_lines": "Detected Line -> Related Ground Truth Line is applied only when category also matches",
            "group_merge_rule": "Predictions are canonicalized by manual equivalent GT-line mapping (e.g., 238->223, 290->286).",
            "actual_evaluation_scis_note": "SCIS comparison is disabled by default; enable via --with-scis.",
            "taint_sanitizer_note": "Taint propagation and sanitizer-recognition scoring is optional and disabled unless --labels-dir is provided.",
            "diting_note": "DITING complementarity compares consensus LLM vs DITING answers on same GT using strict(line+category-set) and line-only.",
            "run_stability_note": "strict_f1 range is computed over the runs used for consensus; strict_jaccard is the mean/min/max pairwise Jaccard similarity over predicted (line, category) sets; line_only_jaccard is the mean/min/max pairwise Jaccard similarity over predicted line sets from those runs.",
        },
        "target_scores": target_scores,
        "diff_vs_scis": diff_vs_scis,
        "diting_complementarity": diting_complementarity,
    }
    if taint_eval_enabled:
        summary["config"]["labels_dir"] = str(args.labels_dir)
        summary["config"]["sanitizer_tolerance"] = args.sanitizer_tolerance

    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    coverage_summary_path = output_dir / "coverage_summary.json"
    coverage_summary_path.write_text(
        json.dumps(summary["coverage"], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    coverage_markdown_path = output_dir / "coverage_summary.md"
    coverage_markdown_path.write_text(
        _render_coverage_markdown(model_root, coverage_aggregate_all_runs, coverage_aggregate_consensus_runs, coverage_rows),
        encoding="utf-8",
    )

    scis_scores_path = None
    if scis_scores:
        scis_scores_path = output_dir / "scis_scores.json"
        scis_scores_path.write_text(json.dumps(scis_scores, ensure_ascii=False, indent=2), encoding="utf-8")

    print("[actual_evaluation] done")
    print(f"  model_root  : {model_root}")
    print(f"  runs_found  : {total_runs}")
    print(f"  consensus   : latest {consensus_window} runs, min_votes={effective_min_votes}")
    print(f"  output_dir  : {output_dir}")
    print(f"  summary     : {summary_path}")
    print(
        "  coverage    : "
        f"avg chains={coverage_aggregate_all_runs['avg_chain_count']:.2f}, "
        f"avg GT coverage={coverage_aggregate_all_runs['avg_covered_gt_line_count']:.2f}/"
        f"{run_coverages[-1]['gt_total_line_count'] if run_coverages else 0} "
        f"({coverage_aggregate_all_runs['avg_coverage_percent']:.2f}%)"
    )
    if diting_complementarity.get("enabled"):
        print(f"  diting      : enabled ({args.diting_csv})")
        for key, path in diting_rows_written.items():
            print(f"    - {key}: {path}")
    else:
        reason = "disabled by --no-diting" if args.no_diting else f"csv not found ({args.diting_csv})"
        print(f"  diting      : disabled ({reason})")
    print(f"  coverage_md : {coverage_markdown_path}")
    print(f"  coverage_js : {coverage_summary_path}")
    if scis_scores_path:
        print(f"  scis_scores : {scis_scores_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
