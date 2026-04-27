#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
bad-partitioning の ta_vulnerabilities.json を比較し、
prompt v1 ベースラインに対する改善/悪化を評価するユーティリティ。

評価軸:
- カテゴリ付き (line, category) 一致
- 行単位 (line) 一致

デフォルト入力:
- baseline: /workspace/prompt_v1_output/gpt5-mini-bad-partitioning/gpt-5-mini-ta_vulnerabilities.json
- ground truth: /workspace/bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


GT_CATEGORIES = {
    "unencrypted_data_output",
    "input_validation_weakness",
    "direct_usage_of_shared_memory",
}


CATEGORY_ALIASES = {
    "udo": "unencrypted_data_output",
    "unencrypted_output": "unencrypted_data_output",
    "unencrypted_data_output": "unencrypted_data_output",
    "unencrypted data output": "unencrypted_data_output",
    "unencrypted data output udo": "unencrypted_data_output",
    "ivw": "input_validation_weakness",
    "wiv": "input_validation_weakness",
    "weak_input_validation": "input_validation_weakness",
    "input_validation_weakness": "input_validation_weakness",
    "input validation weakness": "input_validation_weakness",
    "input validation weakness ivw": "input_validation_weakness",
    "dus": "direct_usage_of_shared_memory",
    "smo": "direct_usage_of_shared_memory",
    "shared_memory_overwrite": "direct_usage_of_shared_memory",
    "shared memory overwrite": "direct_usage_of_shared_memory",
    "direct_usage_of_shared_memory": "direct_usage_of_shared_memory",
    "direct usage of shared memory": "direct_usage_of_shared_memory",
    "direct usage of shared memory dus": "direct_usage_of_shared_memory",
}


@dataclass(frozen=True, order=True)
class Pair:
    line: int
    category: str


def normalize_category(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    raw_key = value.strip().lower()
    raw_key = re.sub(r"\s*\([^)]*\)\s*$", "", raw_key).strip()
    normalized_key = re.sub(r"[\s\-]+", "_", raw_key)
    normalized_key = re.sub(r"_+", "_", normalized_key).strip("_")
    mapped = CATEGORY_ALIASES.get(raw_key) or CATEGORY_ALIASES.get(normalized_key) or normalized_key
    return mapped if mapped in GT_CATEGORIES else None


def parse_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        m = re.search(r"-?\d+", value.strip())
        if m:
            try:
                return int(m.group(0))
            except ValueError:
                return None
    return None


def extract_lines(value: Any) -> List[int]:
    lines: Set[int] = set()

    def _walk(v: Any):
        if isinstance(v, list):
            for x in v:
                _walk(x)
            return
        if isinstance(v, str) and "," in v:
            for part in v.split(","):
                _walk(part)
            return
        iv = parse_int(v)
        if iv is not None:
            lines.add(iv)

    _walk(value)
    return sorted(lines)


def iter_categories(entry: Dict[str, Any]) -> Iterable[str]:
    # vulnerabilities
    for rid in entry.get("rule_ids", []) or []:
        cat = normalize_category(rid)
        if cat:
            yield cat
    # structural_risks
    for rid in entry.get("rules", []) or []:
        cat = normalize_category(rid)
        if cat:
            yield cat

    cat = normalize_category(entry.get("primary_rule_id") or entry.get("primary_rule"))
    if cat:
        yield cat

    # 念のため distribution のキーも拾う
    for rid in (entry.get("rule_distribution") or {}).keys():
        cat = normalize_category(rid)
        if cat:
            yield cat


def load_vulnerability_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def extract_pairs_from_vuln_json(data: Dict[str, Any]) -> Set[Pair]:
    pairs: Set[Pair] = set()
    vulns = data.get("vulnerabilities", []) or []
    risks = data.get("structural_risks", []) or []

    for entry in list(vulns) + list(risks):
        if not isinstance(entry, dict):
            continue
        lines = extract_lines(entry.get("line"))
        if not lines:
            continue
        cats = set(iter_categories(entry))
        if not cats:
            continue
        for ln in lines:
            for cat in cats:
                pairs.add(Pair(ln, cat))
    return pairs


def load_ground_truth_pairs(csv_path: Path) -> Tuple[Set[Pair], Dict[Pair, Dict[str, str]]]:
    gt_pairs: Set[Pair] = set()
    meta: Dict[Pair, Dict[str, str]] = {}
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            line = parse_int(row.get("Line Number"))
            cat = normalize_category(row.get("Category"))
            if line is None or not cat:
                continue
            pair = Pair(line, cat)
            gt_pairs.add(pair)
            if pair not in meta:
                meta[pair] = {
                    "Function": row.get("Function", ""),
                    "Label ID": row.get("Label ID", ""),
                    "Group": row.get("Group", ""),
                    "Category_JP": row.get("Category_JP", ""),
                }
    return gt_pairs, meta


def metrics(pred: Set[Pair], gt: Set[Pair]) -> Dict[str, Any]:
    tp = pred & gt
    fp = pred - gt
    fn = gt - pred
    p = len(tp) / len(pred) if pred else 0.0
    r = len(tp) / len(gt) if gt else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": p,
        "recall": r,
        "f1": f1,
        "pred_count": len(pred),
        "gt_count": len(gt),
    }


def line_metrics(pred: Set[Pair], gt: Set[Pair]) -> Dict[str, Any]:
    pred_lines = {x.line for x in pred}
    gt_lines = {x.line for x in gt}
    tp = pred_lines & gt_lines
    fp = pred_lines - gt_lines
    fn = gt_lines - pred_lines
    p = len(tp) / len(pred_lines) if pred_lines else 0.0
    r = len(tp) / len(gt_lines) if gt_lines else 0.0
    f1 = (2 * p * r / (p + r)) if (p + r) > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": p,
        "recall": r,
        "f1": f1,
        "pred_count": len(pred_lines),
        "gt_count": len(gt_lines),
    }


def resolve_current_vuln_path(current: Path) -> Path:
    if current.is_file():
        return current

    direct = current / "ta_vulnerabilities.json"
    if direct.exists():
        return direct

    candidates: List[Tuple[int, Path]] = []
    for d in current.glob("results_*"):
        if not d.is_dir():
            continue
        m = re.match(r"results_(\d+)$", d.name)
        if not m:
            continue
        p = d / "ta_vulnerabilities.json"
        if p.exists():
            candidates.append((int(m.group(1)), p))

    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    raise FileNotFoundError(f"ta_vulnerabilities.json not found under: {current}")


def to_float4(v: float) -> float:
    return round(v, 4)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Compare current ta_vulnerabilities.json vs prompt_v1 baseline with ground truth labels."
    )
    parser.add_argument(
        "--current",
        required=True,
        type=Path,
        help="Current ta_vulnerabilities.json path OR results_* directory OR model root directory.",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("/workspace/prompt_v1_output/gpt5-mini-bad-partitioning/gpt-5-mini-ta_vulnerabilities.json"),
        help="Baseline ta_vulnerabilities.json path (default: prompt_v1_output gpt-5-mini).",
    )
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("/workspace/bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv"),
        help="Ground truth labels CSV path.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Output directory (default: sibling compare_with_v1 under current results dir).",
    )
    args = parser.parse_args()

    current_json = resolve_current_vuln_path(args.current)
    if not args.baseline.exists():
        raise FileNotFoundError(f"baseline not found: {args.baseline}")
    if not args.ground_truth.exists():
        raise FileNotFoundError(f"ground truth not found: {args.ground_truth}")

    out_dir = args.output_dir or (current_json.parent / "compare_with_v1")
    out_dir.mkdir(parents=True, exist_ok=True)

    current_data = load_vulnerability_json(current_json)
    baseline_data = load_vulnerability_json(args.baseline)
    gt_pairs, gt_meta = load_ground_truth_pairs(args.ground_truth)

    current_pairs = extract_pairs_from_vuln_json(current_data)
    baseline_pairs = extract_pairs_from_vuln_json(baseline_data)

    cur_m = metrics(current_pairs, gt_pairs)
    base_m = metrics(baseline_pairs, gt_pairs)
    cur_lm = line_metrics(current_pairs, gt_pairs)
    base_lm = line_metrics(baseline_pairs, gt_pairs)

    f1_delta = cur_m["f1"] - base_m["f1"]
    lf1_delta = cur_lm["f1"] - base_lm["f1"]
    if f1_delta > 0:
        verdict = "improved"
    elif f1_delta < 0:
        verdict = "regressed"
    else:
        verdict = "no_change"

    summary = {
        "current_json": str(current_json),
        "baseline_json": str(args.baseline),
        "ground_truth_csv": str(args.ground_truth),
        "verdict_category_pair": verdict,
        "delta": {
            "f1": to_float4(f1_delta),
            "line_f1": to_float4(lf1_delta),
            "tp": len(cur_m["tp"]) - len(base_m["tp"]),
            "fp": len(cur_m["fp"]) - len(base_m["fp"]),
            "fn": len(cur_m["fn"]) - len(base_m["fn"]),
        },
        "current": {
            "pair_metrics": {
                "precision": to_float4(cur_m["precision"]),
                "recall": to_float4(cur_m["recall"]),
                "f1": to_float4(cur_m["f1"]),
                "tp": len(cur_m["tp"]),
                "fp": len(cur_m["fp"]),
                "fn": len(cur_m["fn"]),
                "pred_count": cur_m["pred_count"],
                "gt_count": cur_m["gt_count"],
            },
            "line_metrics": {
                "precision": to_float4(cur_lm["precision"]),
                "recall": to_float4(cur_lm["recall"]),
                "f1": to_float4(cur_lm["f1"]),
                "tp": len(cur_lm["tp"]),
                "fp": len(cur_lm["fp"]),
                "fn": len(cur_lm["fn"]),
                "pred_count": cur_lm["pred_count"],
                "gt_count": cur_lm["gt_count"],
            },
        },
        "baseline": {
            "pair_metrics": {
                "precision": to_float4(base_m["precision"]),
                "recall": to_float4(base_m["recall"]),
                "f1": to_float4(base_m["f1"]),
                "tp": len(base_m["tp"]),
                "fp": len(base_m["fp"]),
                "fn": len(base_m["fn"]),
                "pred_count": base_m["pred_count"],
                "gt_count": base_m["gt_count"],
            },
            "line_metrics": {
                "precision": to_float4(base_lm["precision"]),
                "recall": to_float4(base_lm["recall"]),
                "f1": to_float4(base_lm["f1"]),
                "tp": len(base_lm["tp"]),
                "fp": len(base_lm["fp"]),
                "fn": len(base_lm["fn"]),
                "pred_count": base_lm["pred_count"],
                "gt_count": base_lm["gt_count"],
            },
        },
    }

    # 差分CSV
    diff_rows: List[Dict[str, Any]] = []

    def add_rows(items: Set[Pair], change_type: str):
        for pair in sorted(items):
            meta = gt_meta.get(pair, {})
            diff_rows.append(
                {
                    "change_type": change_type,
                    "line": pair.line,
                    "category": pair.category,
                    "function": meta.get("Function", ""),
                    "label_id": meta.get("Label ID", ""),
                    "group": meta.get("Group", ""),
                }
            )

    add_rows(cur_m["tp"] - base_m["tp"], "new_true_positive")
    add_rows(base_m["tp"] - cur_m["tp"], "lost_true_positive")
    add_rows(base_m["fp"] - cur_m["fp"], "false_positive_removed")
    add_rows(cur_m["fp"] - base_m["fp"], "new_false_positive")

    # ground truth ラベルごとの比較CSV
    gt_rows: List[Dict[str, Any]] = []
    for pair in sorted(gt_pairs):
        in_cur = pair in cur_m["tp"]
        in_base = pair in base_m["tp"]
        if in_cur and not in_base:
            status = "improved"
        elif in_base and not in_cur:
            status = "regressed"
        else:
            status = "no_change"
        meta = gt_meta.get(pair, {})
        gt_rows.append(
            {
                "line": pair.line,
                "category": pair.category,
                "function": meta.get("Function", ""),
                "label_id": meta.get("Label ID", ""),
                "group": meta.get("Group", ""),
                "baseline_hit": int(in_base),
                "current_hit": int(in_cur),
                "status": status,
            }
        )

    summary_path = out_dir / "comparison_summary.json"
    diff_path = out_dir / "comparison_diffs.csv"
    gt_path = out_dir / "ground_truth_comparison.csv"

    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    with diff_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["change_type", "line", "category", "function", "label_id", "group"],
        )
        writer.writeheader()
        writer.writerows(diff_rows)

    with gt_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "line",
                "category",
                "function",
                "label_id",
                "group",
                "baseline_hit",
                "current_hit",
                "status",
            ],
        )
        writer.writeheader()
        writer.writerows(gt_rows)

    print("[compare_prompt_versions] Comparison finished")
    print(f"  current   : {current_json}")
    print(f"  baseline  : {args.baseline}")
    print(f"  groundtruth: {args.ground_truth}")
    print(f"  verdict   : {summary['verdict_category_pair']}")
    print(f"  delta F1  : {summary['delta']['f1']:+.4f} (pair), {summary['delta']['line_f1']:+.4f} (line)")
    print(f"  outputs   : {summary_path}, {diff_path}, {gt_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
