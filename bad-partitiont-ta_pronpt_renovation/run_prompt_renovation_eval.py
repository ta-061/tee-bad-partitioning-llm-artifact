#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Set, Tuple


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
COMMON_DIR = WORKSPACE_ROOT / "bad-partitiont-ta_actual_evaluation"
if str(COMMON_DIR) not in sys.path:
    sys.path.insert(0, str(COMMON_DIR))

from evaluation_common import (  # noqa: E402
    Pair,
    apply_group_canonical_map,
    build_group_canonical_pair_map,
    build_taint_sanitizer_eval,
    build_vulnerability_eval,
    delta_verdict,
    line_category_set_metrics,
    line_metrics_from_lines,
    load_ground_truth_pairs,
    load_partial_match_map,
    metrics,
    normalize_category,
    parse_int,
    resolve_results_dir,
    resolve_conversations_path,
    summarize_candidate_flow_coverage,
    resolve_vulnerabilities_path,
    to4,
    write_csv,
)


DEFAULT_GT = Path("/workspace/bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv")
DEFAULT_PARTIAL = Path("/workspace/bad-partitioning-ta_groundtruth_labels/category_labels/partial_match_lines.csv")
DEFAULT_LABELS = Path("/workspace/bad-partitioning-ta_groundtruth_labels/flow_labels/taint_sanitizer_labels")
DEFAULT_DITING = Path("/workspace/src/metrics/DITING_ans.csv")
DEFAULT_DITING_PROJECTS = "bad-partitioning,badpartitioning"
DEFAULT_SCIS_VULN = Path(
    "/workspace/SCIS2026-bad-partitioning-ta_LLMs_output/gpt5-mini-bad-partitioning/gpt-5-mini-ta_vulnerabilities.json"
)
DEFAULT_SCIS_CONV = Path(
    "/workspace/SCIS2026-bad-partitioning-ta_LLMs_output/gpt5-mini-bad-partitioning/gpt-5-mini-conversations.jsonl"
)


def _safe_name(path: Path) -> str:
    if path.is_file():
        return path.parent.name or "current"
    return path.name or "current"


@dataclass
class EvalResult:
    target: Path
    out_dir: Path
    current_vuln: Path
    current_conv: Path
    summary_path: Path
    scis_scores_path: Path
    coverage_summary_path: Path
    pair_delta: float
    line_delta: float
    taint_delta: float
    sanitizer_delta: float
    diting_enabled: bool
    diting_rows_written: Dict[str, str]
    phase3_profile: str
    phase3_profile_source: str
    chain_count: int
    covered_gt_line_count: int
    gt_total_line_count: int
    coverage_percent: float
    uncovered_functions: List[str]


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


def _line_hit_category_precision(strict_metric: Dict[str, Any], line_metric: Dict[str, Any]) -> Dict[str, Any]:
    denominator = line_metric["tp"]
    value = (strict_metric["tp"] / denominator) if denominator > 0 else 0.0
    return {
        "value": to4(value),
        "strict_tp": strict_metric["tp"],
        "line_tp": denominator,
    }


def _status(current_hit: bool, baseline_hit: bool) -> str:
    if current_hit and not baseline_hit:
        return "improved"
    if baseline_hit and not current_hit:
        return "regressed"
    return "no_change"


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


def _is_single_eval_target(path: Path) -> bool:
    try:
        resolve_vulnerabilities_path(path)
        resolve_conversations_path(path)
        return True
    except (FileNotFoundError, ValueError):
        return False


def _discover_child_targets(root: Path) -> List[Path]:
    targets: List[Path] = []
    if not root.is_dir():
        return targets

    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith("."):
            continue
        if _is_single_eval_target(child):
            targets.append(child)
    return targets


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


def _render_coverage_markdown(title: str, coverage: Dict[str, Any]) -> str:
    uncovered_functions = ", ".join(coverage["uncovered_functions"]) or "(none)"
    uncovered_lines = ", ".join(str(line) for line in coverage["uncovered_gt_lines"]) or "(none)"
    return "\n".join(
        [
            f"# {title}",
            "",
            f"- Phase 3 profile (inferred): {coverage['phase3_profile_inferred']}",
            f"- Phase 3 profile source: {coverage['phase3_profile_source']}",
            f"- Analysis mode: {coverage['analysis_mode'] or 'unknown'}",
            f"- Sink count: {coverage['sink_count']}",
            f"- Candidate chain count: {coverage['chain_count']}",
            (
                f"- Ground-truth coverage: {coverage['covered_gt_line_count']}/"
                f"{coverage['gt_total_line_count']} ({coverage['coverage_percent']:.1f}%)"
            ),
            f"- Coverage basis: {coverage['coverage_basis']}",
            f"- Uncovered function count: {coverage['uncovered_gt_function_count']}",
            f"- Uncovered functions: {uncovered_functions}",
            f"- Uncovered GT lines: {uncovered_lines}",
        ]
    ) + "\n"


def _coverage_title(current_target: Path) -> str:
    if current_target.name.startswith("results_") and current_target.parent.name:
        return current_target.parent.name
    return current_target.name


def _aggregate_coverages(items: List[Dict[str, Any]]) -> Dict[str, Any]:
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

    def _avg(values: List[float]) -> float:
        return sum(values) / len(values) if values else 0.0

    return {
        "run_count_total": len(items),
        "run_count_available": len(available_items),
        "run_count_skipped": len(items) - len(available_items),
        "avg_chain_count": to4(_avg([float(v) for v in chain_counts])),
        "min_chain_count": min(chain_counts),
        "max_chain_count": max(chain_counts),
        "avg_sink_count": to4(_avg([float(v) for v in sink_counts])),
        "min_sink_count": min(sink_counts),
        "max_sink_count": max(sink_counts),
        "avg_covered_gt_line_count": to4(_avg([float(v) for v in covered_counts])),
        "min_covered_gt_line_count": min(covered_counts),
        "max_covered_gt_line_count": max(covered_counts),
        "avg_coverage_percent": to4(_avg(coverage_percents)),
        "min_coverage_percent": to4(min(coverage_percents)),
        "max_coverage_percent": to4(max(coverage_percents)),
    }


def _coverage_frequency_rows(items: List[Dict[str, Any]], gt_meta: Dict[Pair, Dict[str, str]]) -> List[Dict[str, Any]]:
    function_names = sorted({(meta.get("function") or "").strip() for meta in gt_meta.values() if (meta.get("function") or "").strip()})
    available_items = [item for item in items if item.get("coverage_available")]
    counts: Dict[str, int] = defaultdict(int)
    for item in available_items:
        for function_name in item.get("uncovered_functions", []):
            counts[function_name] += 1
    rows: List[Dict[str, Any]] = []
    run_count = len(available_items)
    for function_name in function_names:
        missing = counts.get(function_name, 0)
        rows.append(
            {
                "function": function_name,
                "runs_missing": missing,
                "runs_covering": run_count - missing,
                "missing_ratio": to4(missing / run_count if run_count else 0.0),
            }
        )
    return rows


def _coverage_per_run_row(run_name: str, coverage: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "run_name": run_name,
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


def evaluate_target(args: argparse.Namespace, current_target: Path, out_dir: Path) -> EvalResult:
    current_vuln = resolve_vulnerabilities_path(current_target)
    current_conv = resolve_conversations_path(current_target)
    results_dir = resolve_results_dir(current_target)

    out_dir.mkdir(parents=True, exist_ok=True)

    gt_pairs, gt_meta, gt_line_to_categories = load_ground_truth_pairs(args.ground_truth)
    partial_map = load_partial_match_map(args.partial_match, gt_line_to_categories)
    group_canonical_map = build_group_canonical_pair_map(gt_meta)
    coverage = summarize_candidate_flow_coverage(results_dir, gt_meta)

    current_v = build_vulnerability_eval(
        current_vuln,
        gt_pairs,
        partial_map=partial_map,
        canonical_pair_map=group_canonical_map,
    )
    scis_v = build_vulnerability_eval(
        args.scis_vuln,
        gt_pairs,
        partial_map=partial_map,
        canonical_pair_map=group_canonical_map,
    )

    current_ts = build_taint_sanitizer_eval(current_conv, args.labels_dir, sanitizer_tolerance=args.sanitizer_tolerance)
    scis_ts = build_taint_sanitizer_eval(args.scis_conversations, args.labels_dir, sanitizer_tolerance=args.sanitizer_tolerance)

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

        _diting_pair_metrics_raw = metrics(diting_pairs, gt_pairs)
        _diting_line_metrics_raw = line_metrics_from_lines(diting_lines, gt_pairs)
        _diting_strict_metrics_raw = line_category_set_metrics(diting_lines, diting_pairs, gt_line_to_categories)

        combined_pairs = set(current_v["pred_pairs"]) | diting_pairs
        combined_lines = set(current_v["pred_lines_all"]) | diting_lines
        _combined_pair_metrics_raw = metrics(combined_pairs, gt_pairs)
        _combined_line_metrics_raw = line_metrics_from_lines(combined_lines, gt_pairs)
        _combined_strict_metrics_raw = line_category_set_metrics(combined_lines, combined_pairs, gt_line_to_categories)

        gt_lines = set(gt_line_to_categories.keys())
        strict_comp = _complementarity_block(
            current_v["strict_metrics"]["tp_set"],
            _diting_strict_metrics_raw["tp_set"],
            gt_lines,
        )
        line_comp = _complementarity_block(
            current_v["line_metrics"]["tp_set"],
            _diting_line_metrics_raw["tp_set"],
            gt_lines,
        )

        pair_breakdown_rows: List[Dict[str, Any]] = []
        for pair in sorted(gt_pairs):
            llm_strict_hit = pair.line in current_v["strict_metrics"]["tp_set"]
            diting_strict_hit = pair.line in _diting_strict_metrics_raw["tp_set"]
            llm_line_hit = pair.line in current_v["line_metrics"]["tp_set"]
            diting_line_hit = pair.line in _diting_line_metrics_raw["tp_set"]
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

        pair_breakdown_csv = out_dir / "diting_llm_gt_pair_breakdown.csv"
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

        characteristics_csv = out_dir / "diting_llm_bucket_characteristics.csv"
        write_csv(
            characteristics_csv,
            fieldnames=["scope", "metric", "bucket", "key", "count", "bucket_total", "ratio_in_bucket"],
            rows=characteristics_rows,
        )

        pred_overlap_rows: List[Dict[str, Any]] = []
        pred_universe = set(current_v["pred_pairs"]) | set(diting_pairs) | set(gt_pairs)
        for pair in sorted(pred_universe):
            in_llm = pair in current_v["pred_pairs"]
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

        pred_overlap_csv = out_dir / "diting_llm_prediction_overlap.csv"
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
                "strict_line_category": "line+category-set overlap match (same as strict metric)",
                "line_only": "line localization match (category ignored)",
            },
            "llm_only": {
                "strict_line_category": _metric_block(current_v["strict_metrics"]),
                "line_only": _line_metric_block(current_v["line_metrics"]),
                "pair": _metric_block(current_v["pair_metrics"]),
            },
            "diting_only": {
                "strict_line_category": _metric_block(_diting_strict_metrics_raw),
                "line_only": _line_metric_block(_diting_line_metrics_raw),
                "pair": _metric_block(_diting_pair_metrics_raw),
            },
            "combined_union": {
                "strict_line_category": _metric_block(_combined_strict_metrics_raw),
                "line_only": _line_metric_block(_combined_line_metrics_raw),
                "pair": _metric_block(_combined_pair_metrics_raw),
                "delta_vs_llm": {
                    "strict_tp": _combined_strict_metrics_raw["tp"] - current_v["strict_metrics"]["tp"],
                    "strict_recall": to4(_combined_strict_metrics_raw["recall"] - current_v["strict_metrics"]["recall"]),
                    "strict_f1": to4(_combined_strict_metrics_raw["f1"] - current_v["strict_metrics"]["f1"]),
                    "line_tp": _combined_line_metrics_raw["tp"] - current_v["line_metrics"]["tp"],
                    "line_recall": to4(_combined_line_metrics_raw["recall"] - current_v["line_metrics"]["recall"]),
                    "line_f1": to4(_combined_line_metrics_raw["f1"] - current_v["line_metrics"]["f1"]),
                },
                "delta_vs_diting": {
                    "strict_tp": _combined_strict_metrics_raw["tp"] - _diting_strict_metrics_raw["tp"],
                    "strict_recall": to4(_combined_strict_metrics_raw["recall"] - _diting_strict_metrics_raw["recall"]),
                    "strict_f1": to4(_combined_strict_metrics_raw["f1"] - _diting_strict_metrics_raw["f1"]),
                    "line_tp": _combined_line_metrics_raw["tp"] - _diting_line_metrics_raw["tp"],
                    "line_recall": to4(_combined_line_metrics_raw["recall"] - _diting_line_metrics_raw["recall"]),
                    "line_f1": to4(_combined_line_metrics_raw["f1"] - _diting_line_metrics_raw["f1"]),
                },
            },
            "overlap_on_ground_truth": {
                "strict_line_category": strict_comp,
                "line_only": line_comp,
            },
            "outputs": diting_rows_written,
        }

    pair_delta = current_v["strict_metrics"]["f1"] - scis_v["strict_metrics"]["f1"]
    line_delta = current_v["line_metrics"]["f1"] - scis_v["line_metrics"]["f1"]
    taint_delta = current_ts["taint_metrics"]["f1"] - scis_ts["taint_metrics"]["f1"]
    sanitizer_delta = current_ts["sanitizer_metrics"]["f1"] - scis_ts["sanitizer_metrics"]["f1"]

    summary = {
        "current": {
            "vulnerability_json": str(current_vuln),
            "conversations_jsonl": str(current_conv),
        },
        "scis_baseline": {
            "vulnerability_json": str(args.scis_vuln),
            "conversations_jsonl": str(args.scis_conversations),
        },
        "gold_labels": {
            "category_ground_truth": str(args.ground_truth),
            "partial_match": str(args.partial_match),
            "taint_sanitizer_labels_dir": str(args.labels_dir),
        },
        "config": {
            "sanitizer_tolerance": args.sanitizer_tolerance,
            "group_merge_enabled": True,
            "group_merge_pair_mappings": len(group_canonical_map),
            "diting_csv": str(args.diting_csv),
            "diting_projects": args.diting_projects,
            "diting_enabled": diting_enabled,
        },
        "scoring_policy": {
            "strict_metric": "line+category-set overlap match",
            "line_only_metric": "line localization match over all detected lines (category ignored; includes other)",
            "line_hit_category_precision": "strict_tp / line_tp",
            "group_merge_rule": "Predictions are canonicalized by manual equivalent GT-line mapping (e.g., 238->223, 290->286).",
            "diting_note": "DITING complementarity compares current LLM run vs DITING answers on same GT using strict and line-only metrics.",
        },
        "verdict": {
            "strict_line_category_f1": delta_verdict(pair_delta),
            "line_f1": delta_verdict(line_delta),
            "taint_f1": delta_verdict(taint_delta),
            "sanitizer_f1": delta_verdict(sanitizer_delta),
        },
        "delta": {
            "strict_line_category_f1": to4(pair_delta),
            "line_f1": to4(line_delta),
            "taint_f1": to4(taint_delta),
            "sanitizer_f1": to4(sanitizer_delta),
        },
        "coverage": coverage,
        "current_metrics": {
            "vulnerability_all": {
                "strict_line_category": _metric_block(current_v["strict_metrics"]),
                "line_only": _metric_block(current_v["line_metrics"]),
                "line_hit_category_precision": _line_hit_category_precision(
                    current_v["strict_metrics"], current_v["line_metrics"]
                ),
            },
            "vulnerability_by_category": _category_block(current_v["category_metrics"]),
            "taint": {
                "tp": current_ts["taint_metrics"]["tp"],
                "fp": current_ts["taint_metrics"]["fp"],
                "fn": current_ts["taint_metrics"]["fn"],
                "expected_count": current_ts["taint_metrics"]["expected_count"],
                "precision": to4(current_ts["taint_metrics"]["precision"]),
                "recall": to4(current_ts["taint_metrics"]["recall"]),
                "f1": to4(current_ts["taint_metrics"]["f1"]),
            },
            "sanitizer": {
                "tp": current_ts["sanitizer_metrics"]["tp"],
                "fp": current_ts["sanitizer_metrics"]["fp"],
                "fn": current_ts["sanitizer_metrics"]["fn"],
                "expected_count": current_ts["sanitizer_metrics"]["expected_count"],
                "precision": to4(current_ts["sanitizer_metrics"]["precision"]),
                "recall": to4(current_ts["sanitizer_metrics"]["recall"]),
                "f1": to4(current_ts["sanitizer_metrics"]["f1"]),
            },
        },
        "scis_metrics": {
            "vulnerability_all": {
                "strict_line_category": _metric_block(scis_v["strict_metrics"]),
                "line_only": _metric_block(scis_v["line_metrics"]),
                "line_hit_category_precision": _line_hit_category_precision(scis_v["strict_metrics"], scis_v["line_metrics"]),
            },
            "vulnerability_by_category": _category_block(scis_v["category_metrics"]),
            "taint": {
                "tp": scis_ts["taint_metrics"]["tp"],
                "fp": scis_ts["taint_metrics"]["fp"],
                "fn": scis_ts["taint_metrics"]["fn"],
                "expected_count": scis_ts["taint_metrics"]["expected_count"],
                "precision": to4(scis_ts["taint_metrics"]["precision"]),
                "recall": to4(scis_ts["taint_metrics"]["recall"]),
                "f1": to4(scis_ts["taint_metrics"]["f1"]),
            },
            "sanitizer": {
                "tp": scis_ts["sanitizer_metrics"]["tp"],
                "fp": scis_ts["sanitizer_metrics"]["fp"],
                "fn": scis_ts["sanitizer_metrics"]["fn"],
                "expected_count": scis_ts["sanitizer_metrics"]["expected_count"],
                "precision": to4(scis_ts["sanitizer_metrics"]["precision"]),
                "recall": to4(scis_ts["sanitizer_metrics"]["recall"]),
                "f1": to4(scis_ts["sanitizer_metrics"]["f1"]),
            },
        },
        "diting_complementarity": diting_complementarity,
    }

    summary_path = out_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    coverage_row = _coverage_per_run_row(results_dir.name, coverage)
    coverage_summary = {
        "schema_version": 1,
        "coverage_mode": "single_run",
        "coverage_basis": coverage["coverage_basis"],
        "aggregate_all_runs": _aggregate_coverages([coverage]),
        "aggregate_selected_runs": _aggregate_coverages([coverage]),
        "aggregate_consensus_runs": _aggregate_coverages([coverage]),
        "latest_run": coverage,
        "results": [coverage_row],
        "per_run": [coverage_row],
        "uncovered_function_frequency_all_runs": _coverage_frequency_rows([coverage], gt_meta),
        "uncovered_function_frequency_selected_runs": _coverage_frequency_rows([coverage], gt_meta),
        "uncovered_function_frequency_consensus_runs": _coverage_frequency_rows([coverage], gt_meta),
    }

    coverage_summary_path = out_dir / "coverage_summary.json"
    coverage_summary_path.write_text(json.dumps(coverage_summary, ensure_ascii=False, indent=2), encoding="utf-8")
    coverage_markdown_path = out_dir / "coverage_summary.md"
    coverage_markdown_path.write_text(
        _render_coverage_markdown(f"Coverage Summary: {_coverage_title(current_target)}", coverage),
        encoding="utf-8",
    )

    scis_scores = {
        "source": {
            "vulnerability_json": str(args.scis_vuln),
            "conversations_jsonl": str(args.scis_conversations),
        },
        "vulnerability_all": summary["scis_metrics"]["vulnerability_all"],
        "vulnerability_by_category": summary["scis_metrics"]["vulnerability_by_category"],
        "taint_propagation": summary["scis_metrics"]["taint"],
        "sanitizer_recognition": summary["scis_metrics"]["sanitizer"],
    }
    scis_scores_path = out_dir / "scis_scores.json"
    scis_scores_path.write_text(json.dumps(scis_scores, ensure_ascii=False, indent=2), encoding="utf-8")

    category_rows: List[Dict[str, Any]] = []
    for category in sorted(current_v["category_metrics"].keys()):
        cur_cat = current_v["category_metrics"][category]
        scis_cat = scis_v["category_metrics"][category]
        category_rows.append(
            {
                "scope": "category_pair",
                "category": category,
                "current_tp": cur_cat["tp"],
                "current_fp": cur_cat["fp"],
                "current_fn": cur_cat["fn"],
                "current_precision": to4(cur_cat["precision"]),
                "current_recall": to4(cur_cat["recall"]),
                "current_f1": to4(cur_cat["f1"]),
                "scis_tp": scis_cat["tp"],
                "scis_fp": scis_cat["fp"],
                "scis_fn": scis_cat["fn"],
                "scis_precision": to4(scis_cat["precision"]),
                "scis_recall": to4(scis_cat["recall"]),
                "scis_f1": to4(scis_cat["f1"]),
                "delta_f1": to4(cur_cat["f1"] - scis_cat["f1"]),
                "verdict": delta_verdict(cur_cat["f1"] - scis_cat["f1"]),
            }
        )

    category_rows.append(
        {
            "scope": "overall_strict_line_category",
            "category": "all",
            "current_tp": current_v["strict_metrics"]["tp"],
            "current_fp": current_v["strict_metrics"]["fp"],
            "current_fn": current_v["strict_metrics"]["fn"],
            "current_precision": to4(current_v["strict_metrics"]["precision"]),
            "current_recall": to4(current_v["strict_metrics"]["recall"]),
            "current_f1": to4(current_v["strict_metrics"]["f1"]),
            "scis_tp": scis_v["strict_metrics"]["tp"],
            "scis_fp": scis_v["strict_metrics"]["fp"],
            "scis_fn": scis_v["strict_metrics"]["fn"],
            "scis_precision": to4(scis_v["strict_metrics"]["precision"]),
            "scis_recall": to4(scis_v["strict_metrics"]["recall"]),
            "scis_f1": to4(scis_v["strict_metrics"]["f1"]),
            "delta_f1": to4(pair_delta),
            "verdict": delta_verdict(pair_delta),
        }
    )
    category_rows.append(
        {
            "scope": "overall_line",
            "category": "all",
            "current_tp": current_v["line_metrics"]["tp"],
            "current_fp": current_v["line_metrics"]["fp"],
            "current_fn": current_v["line_metrics"]["fn"],
            "current_precision": to4(current_v["line_metrics"]["precision"]),
            "current_recall": to4(current_v["line_metrics"]["recall"]),
            "current_f1": to4(current_v["line_metrics"]["f1"]),
            "scis_tp": scis_v["line_metrics"]["tp"],
            "scis_fp": scis_v["line_metrics"]["fp"],
            "scis_fn": scis_v["line_metrics"]["fn"],
            "scis_precision": to4(scis_v["line_metrics"]["precision"]),
            "scis_recall": to4(scis_v["line_metrics"]["recall"]),
            "scis_f1": to4(scis_v["line_metrics"]["f1"]),
            "delta_f1": to4(line_delta),
            "verdict": delta_verdict(line_delta),
        }
    )

    category_csv = out_dir / "category_metrics_comparison.csv"
    write_csv(
        category_csv,
        fieldnames=[
            "scope",
            "category",
            "current_tp",
            "current_fp",
            "current_fn",
            "current_precision",
            "current_recall",
            "current_f1",
            "scis_tp",
            "scis_fp",
            "scis_fn",
            "scis_precision",
            "scis_recall",
            "scis_f1",
            "delta_f1",
            "verdict",
        ],
        rows=category_rows,
    )

    gt_rows: List[Dict[str, Any]] = []
    for pair in sorted(gt_pairs):
        in_current = pair.line in current_v["strict_metrics"]["tp_set"]
        in_scis = pair.line in scis_v["strict_metrics"]["tp_set"]
        meta = gt_meta.get(pair, {})
        gt_rows.append(
            {
                "line": pair.line,
                "category": pair.category,
                "function": meta.get("function", ""),
                "label_id": meta.get("label_id", ""),
                "group": meta.get("group", ""),
                "scis_hit": int(in_scis),
                "current_hit": int(in_current),
                "status": _status(in_current, in_scis),
            }
        )

    gt_csv = out_dir / "ground_truth_hit_comparison.csv"
    write_csv(
        gt_csv,
        fieldnames=["line", "category", "function", "label_id", "group", "scis_hit", "current_hit", "status"],
        rows=gt_rows,
    )

    diff_rows: List[Dict[str, Any]] = []

    def _add_line_diff(items: set[int], change_type: str):
        for line in sorted(items):
            diff_rows.append(
                {
                    "change_type": change_type,
                    "line": line,
                    "category": "",
                    "function": "",
                    "label_id": "",
                    "group": "",
                }
            )

    _add_line_diff(current_v["strict_metrics"]["tp_set"] - scis_v["strict_metrics"]["tp_set"], "new_true_positive")
    _add_line_diff(scis_v["strict_metrics"]["tp_set"] - current_v["strict_metrics"]["tp_set"], "lost_true_positive")
    _add_line_diff(scis_v["strict_metrics"]["fp_set"] - current_v["strict_metrics"]["fp_set"], "false_positive_removed")
    _add_line_diff(current_v["strict_metrics"]["fp_set"] - scis_v["strict_metrics"]["fp_set"], "new_false_positive")

    diff_csv = out_dir / "prediction_diffs.csv"
    write_csv(
        diff_csv,
        fieldnames=["change_type", "line", "category", "function", "label_id", "group"],
        rows=diff_rows,
    )

    ts_rows = [
        {
            "target": "taint",
            "current_tp": current_ts["taint_metrics"]["tp"],
            "current_fp": current_ts["taint_metrics"]["fp"],
            "current_fn": current_ts["taint_metrics"]["fn"],
            "current_precision": to4(current_ts["taint_metrics"]["precision"]),
            "current_recall": to4(current_ts["taint_metrics"]["recall"]),
            "current_f1": to4(current_ts["taint_metrics"]["f1"]),
            "scis_tp": scis_ts["taint_metrics"]["tp"],
            "scis_fp": scis_ts["taint_metrics"]["fp"],
            "scis_fn": scis_ts["taint_metrics"]["fn"],
            "scis_precision": to4(scis_ts["taint_metrics"]["precision"]),
            "scis_recall": to4(scis_ts["taint_metrics"]["recall"]),
            "scis_f1": to4(scis_ts["taint_metrics"]["f1"]),
            "delta_f1": to4(taint_delta),
            "verdict": delta_verdict(taint_delta),
        },
        {
            "target": "sanitizer",
            "current_tp": current_ts["sanitizer_metrics"]["tp"],
            "current_fp": current_ts["sanitizer_metrics"]["fp"],
            "current_fn": current_ts["sanitizer_metrics"]["fn"],
            "current_precision": to4(current_ts["sanitizer_metrics"]["precision"]),
            "current_recall": to4(current_ts["sanitizer_metrics"]["recall"]),
            "current_f1": to4(current_ts["sanitizer_metrics"]["f1"]),
            "scis_tp": scis_ts["sanitizer_metrics"]["tp"],
            "scis_fp": scis_ts["sanitizer_metrics"]["fp"],
            "scis_fn": scis_ts["sanitizer_metrics"]["fn"],
            "scis_precision": to4(scis_ts["sanitizer_metrics"]["precision"]),
            "scis_recall": to4(scis_ts["sanitizer_metrics"]["recall"]),
            "scis_f1": to4(scis_ts["sanitizer_metrics"]["f1"]),
            "delta_f1": to4(sanitizer_delta),
            "verdict": delta_verdict(sanitizer_delta),
        },
    ]
    ts_csv = out_dir / "taint_sanitizer_comparison.csv"
    write_csv(
        ts_csv,
        fieldnames=[
            "target",
            "current_tp",
            "current_fp",
            "current_fn",
            "current_precision",
            "current_recall",
            "current_f1",
            "scis_tp",
            "scis_fp",
            "scis_fn",
            "scis_precision",
            "scis_recall",
            "scis_f1",
            "delta_f1",
            "verdict",
        ],
        rows=ts_rows,
    )

    print("[prompt_renovation_eval] done")
    print(f"  current_vuln : {current_vuln}")
    print(f"  current_conv : {current_conv}")
    print(f"  output_dir   : {out_dir}")
    print(f"  summary      : {summary_path}")
    print(
        "  coverage     : "
        f"{coverage['phase3_profile_inferred']} / "
        f"{coverage['covered_gt_line_count']}/{coverage['gt_total_line_count']} "
        f"({coverage['coverage_percent']:.1f}%) / chains={coverage['chain_count']}"
    )
    print(f"  scis_scores  : {scis_scores_path}")
    if diting_complementarity.get("enabled"):
        print(f"  diting       : enabled ({args.diting_csv})")
        for key, path in diting_rows_written.items():
            print(f"    - {key}: {path}")
    else:
        reason = "disabled by --no-diting" if args.no_diting else f"csv not found ({args.diting_csv})"
        print(f"  diting       : disabled ({reason})")
    print(f"  delta_f1     : pair={pair_delta:+.4f}, line={line_delta:+.4f}, taint={taint_delta:+.4f}, sanitizer={sanitizer_delta:+.4f}")

    return EvalResult(
        target=current_target,
        out_dir=out_dir,
        current_vuln=current_vuln,
        current_conv=current_conv,
        summary_path=summary_path,
        scis_scores_path=scis_scores_path,
        coverage_summary_path=coverage_summary_path,
        pair_delta=pair_delta,
        line_delta=line_delta,
        taint_delta=taint_delta,
        sanitizer_delta=sanitizer_delta,
        diting_enabled=diting_enabled,
        diting_rows_written=diting_rows_written,
        phase3_profile=coverage["phase3_profile_inferred"],
        phase3_profile_source=coverage["phase3_profile_source"],
        chain_count=coverage["chain_count"],
        covered_gt_line_count=coverage["covered_gt_line_count"],
        gt_total_line_count=coverage["gt_total_line_count"],
        coverage_percent=float(coverage["coverage_percent"]),
        uncovered_functions=coverage["uncovered_functions"],
    )


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


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Evaluate one prompt-renovation result, or batch-evaluate all child experiment "
            "directories under a root, against gold labels and the SCIS2026 gpt-5-mini baseline."
        )
    )
    parser.add_argument(
        "current_path",
        nargs="?",
        type=Path,
        help="Current target path (ta_vulnerabilities.json, results_* dir, or model dir).",
    )
    parser.add_argument(
        "--current",
        type=Path,
        default=None,
        help="Current target path (same as positional argument).",
    )
    parser.add_argument("--scis-vuln", type=Path, default=DEFAULT_SCIS_VULN, help="SCIS baseline ta_vulnerabilities.json.")
    parser.add_argument("--scis-conversations", type=Path, default=DEFAULT_SCIS_CONV, help="SCIS baseline conversations.jsonl.")
    parser.add_argument("--ground-truth", type=Path, default=DEFAULT_GT, help="Ground truth labels CSV.")
    parser.add_argument("--partial-match", type=Path, default=DEFAULT_PARTIAL, help="Partial match mapping CSV.")
    parser.add_argument("--labels-dir", type=Path, default=DEFAULT_LABELS, help="Taint/sanitizer labels directory.")
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
    parser.add_argument("--sanitizer-tolerance", type=int, default=2, help="Line tolerance for sanitizer matching.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help=(
            "Output directory. Single target: writes directly here. "
            "Batch target: writes one subdirectory per child experiment here."
        ),
    )
    args = parser.parse_args()

    if not args.ground_truth.exists():
        raise FileNotFoundError(f"ground truth not found: {args.ground_truth}")
    if not args.labels_dir.exists():
        raise FileNotFoundError(f"labels dir not found: {args.labels_dir}")
    if not args.scis_vuln.exists():
        raise FileNotFoundError(f"SCIS vulnerability json not found: {args.scis_vuln}")
    if not args.scis_conversations.exists():
        raise FileNotFoundError(f"SCIS conversations not found: {args.scis_conversations}")

    current_target = args.current or args.current_path
    if current_target is None:
        parser.error("current path is required (positional or --current).")

    if _is_single_eval_target(current_target):
        out_dir = args.output_dir or (WORKSPACE_ROOT / "bad-partitiont-ta_pronpt_renovation" / _safe_name(current_target))
        evaluate_target(args, current_target, out_dir)
        return 0

    child_targets = _discover_child_targets(current_target)
    if not child_targets:
        raise FileNotFoundError(
            f"No evaluable target found under: {current_target} "
            "(expected a direct run dir or child directories containing results)"
        )

    batch_root = args.output_dir or (WORKSPACE_ROOT / "bad-partitiont-ta_pronpt_renovation" / _safe_name(current_target))
    batch_root.mkdir(parents=True, exist_ok=True)

    successes: List[EvalResult] = []
    result_rows: List[Dict[str, Any]] = []
    failures: List[Dict[str, str]] = []

    print(f"[prompt_renovation_eval] batch mode: {len(child_targets)} targets")
    print(f"  input_root  : {current_target}")
    print(f"  output_root : {batch_root}")

    for target in child_targets:
        out_dir = batch_root / _safe_name(target)
        print(f"\n[batch] evaluating {target.name}")
        try:
            result = evaluate_target(args, target, out_dir)
            successes.append(result)
            result_rows.append(
                {
                    "target": result.target.name,
                    "input_target": str(result.target),
                    "output_dir": str(result.out_dir),
                    "status": "success",
                    "error": "",
                    "summary_json": str(result.summary_path),
                    "coverage_summary_json": str(result.coverage_summary_path),
                    "phase3_profile": result.phase3_profile,
                    "phase3_profile_source": result.phase3_profile_source,
                    "chain_count": result.chain_count,
                    "covered_gt_lines": result.covered_gt_line_count,
                    "gt_total_lines": result.gt_total_line_count,
                    "coverage_percent": to4(result.coverage_percent),
                    "uncovered_functions": ",".join(result.uncovered_functions),
                    "pair_delta_f1": to4(result.pair_delta),
                    "line_delta_f1": to4(result.line_delta),
                    "taint_delta_f1": to4(result.taint_delta),
                    "sanitizer_delta_f1": to4(result.sanitizer_delta),
                    "diting_enabled": int(result.diting_enabled),
                }
            )
        except Exception as exc:
            failures.append({"target": str(target), "error": str(exc)})
            result_rows.append(
                {
                    "target": target.name,
                    "input_target": str(target),
                    "output_dir": str(out_dir),
                    "status": "failed",
                    "error": str(exc),
                    "summary_json": "",
                    "coverage_summary_json": "",
                    "phase3_profile": "",
                    "phase3_profile_source": "",
                    "chain_count": "",
                    "covered_gt_lines": "",
                    "gt_total_lines": "",
                    "coverage_percent": "",
                    "uncovered_functions": "",
                    "pair_delta_f1": "",
                    "line_delta_f1": "",
                    "taint_delta_f1": "",
                    "sanitizer_delta_f1": "",
                    "diting_enabled": "",
                }
            )
            print(f"[batch] failed: {target} -> {exc}")

    batch_csv = batch_root / "batch_summary.csv"
    write_csv(
        batch_csv,
        fieldnames=[
            "target",
            "input_target",
            "output_dir",
            "status",
            "error",
            "summary_json",
            "coverage_summary_json",
            "phase3_profile",
            "phase3_profile_source",
            "chain_count",
            "covered_gt_lines",
            "gt_total_lines",
            "coverage_percent",
            "uncovered_functions",
            "pair_delta_f1",
            "line_delta_f1",
            "taint_delta_f1",
            "sanitizer_delta_f1",
            "diting_enabled",
        ],
        rows=result_rows,
    )

    batch_json = batch_root / "batch_summary.json"
    batch_json.write_text(
        json.dumps(
            {
                "input_root": str(current_target),
                "output_root": str(batch_root),
                "success_count": len(successes),
                "failure_count": len(failures),
                "results": result_rows,
                "successes": [row for row in result_rows if row["status"] == "success"],
                "failures": failures,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("\n[prompt_renovation_eval] batch done")
    print(f"  successes    : {len(successes)}")
    print(f"  failures     : {len(failures)}")
    print(f"  batch_csv    : {batch_csv}")
    print(f"  batch_json   : {batch_json}")
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
