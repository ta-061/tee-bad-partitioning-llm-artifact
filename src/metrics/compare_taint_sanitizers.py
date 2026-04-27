#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
conversations.jsonl からテイント伝播/サニタイズ認識を抽出し、
baseline(prompt_v1) と current を ground truth ラベルで比較する。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


def parse_int(value: Any) -> Optional[int]:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        m = re.search(r"-?\d+", value)
        if m:
            try:
                return int(m.group(0))
            except ValueError:
                return None
    return None


def normalize_var_name(var: str) -> str:
    # Summery script と同等の正規化 + 範囲表記補正
    var = var.strip()
    var = re.sub(r"\[\d+\.\.\d+\]", "[*]", var)
    var = re.sub(r"\[\d+\]", "[*]", var)
    return var


def var_matches(expected: str, detected: str) -> bool:
    if expected == detected:
        return True
    if expected in detected or detected in expected:
        return True
    exp_base = expected.split("[")[0].split(".")[0]
    det_base = detected.split("[")[0].split(".")[0]
    if exp_base and det_base and exp_base == det_base:
        return True
    return False


def extract_json_payload(text: Any) -> Optional[Dict[str, Any]]:
    if isinstance(text, dict):
        return text
    if not isinstance(text, str):
        return None
    s = text.strip()
    s = re.sub(r"^```(?:json)?\s*", "", s)
    s = re.sub(r"\s*```$", "", s)
    try:
        obj = json.loads(s)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            obj = json.loads(match.group(0))
            if isinstance(obj, dict):
                return obj
        except json.JSONDecodeError:
            return None
    return None


def resolve_conversations_path(path: Path) -> Path:
    if path.is_file():
        return path

    direct = path / "conversations.jsonl"
    if direct.exists():
        return direct

    candidates: List[Tuple[int, Path]] = []
    for d in path.glob("results_*"):
        if not d.is_dir():
            continue
        m = re.match(r"results_(\d+)$", d.name)
        if not m:
            continue
        p = d / "conversations.jsonl"
        if p.exists():
            candidates.append((int(m.group(1)), p))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    raise FileNotFoundError(f"conversations.jsonl not found under: {path}")


def parse_site_line(site: str) -> Optional[int]:
    if not isinstance(site, str):
        return None
    return parse_int(site.split(":")[-1] if ":" in site else site)


def iter_sanitizers(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    ta = payload.get("taint_analysis")
    if isinstance(ta, dict):
        for s in ta.get("sanitizers", []) or []:
            if isinstance(s, dict):
                yield s
    for s in payload.get("sanitizers", []) or []:
        if isinstance(s, dict):
            yield s
    for s in payload.get("effective_sanitizers", []) or []:
        if isinstance(s, dict):
            yield s


def collect_detected_from_conversations(path: Path) -> Tuple[Dict[str, Set[str]], Set[Tuple[str, int]]]:
    per_function_taints: Dict[str, Set[str]] = {}
    sanitizer_locs: Set[Tuple[str, int]] = set()

    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if obj.get("type") != "flow_conversations":
                continue
            for conv in obj.get("conversations", []) or []:
                if not isinstance(conv, dict):
                    continue
                payload = extract_json_payload(conv.get("response"))
                if not payload:
                    continue

                func = (
                    (payload.get("taint_analysis") or {}).get("function")
                    or payload.get("function")
                    or conv.get("function")
                    or "unknown"
                )
                if func not in per_function_taints:
                    per_function_taints[func] = set()

                ta = payload.get("taint_analysis")
                tv = []
                if isinstance(ta, dict):
                    tv = ta.get("tainted_vars", []) or []
                if not tv:
                    tv = payload.get("tainted_vars", []) or []

                for var in tv:
                    if isinstance(var, dict):
                        var = var.get("name") or var.get("variable") or var.get("var") or str(var)
                    if not isinstance(var, str):
                        var = str(var)
                    per_function_taints[func].add(normalize_var_name(var))

                for san in iter_sanitizers(payload):
                    location = san.get("location", "")
                    if isinstance(location, str) and ":" in location:
                        parts = location.split(":")
                        s_func = parts[0] or func
                        s_line = parse_int(parts[1]) if len(parts) > 1 else None
                        if s_line is not None:
                            sanitizer_locs.add((s_func, s_line))
                            continue

                    site_line = parse_site_line(san.get("site", ""))
                    if site_line is not None:
                        sanitizer_locs.add((func, site_line))

    return per_function_taints, sanitizer_locs


def load_taint_expected(labels_dir: Path) -> Set[Tuple[str, str]]:
    expected: Set[Tuple[str, str]] = set()
    for p in sorted(labels_dir.glob("*_taint_labels.csv")):
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                func = (row.get("function") or "").strip()
                var_field = (row.get("var") or "").strip()
                if not func or not var_field:
                    continue
                for part in [x.strip() for x in var_field.split(",") if x.strip()]:
                    expected.add((func, normalize_var_name(part)))
    return expected


def load_sanitizer_expected(labels_dir: Path) -> Set[Tuple[str, int]]:
    expected: Set[Tuple[str, int]] = set()
    for p in sorted(labels_dir.glob("*_sanitizer_labels.csv")):
        with p.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                func = (row.get("function") or "").strip()
                line = parse_int(row.get("line"))
                if func and line is not None:
                    expected.add((func, line))
    return expected


def evaluate_taint(expected: Set[Tuple[str, str]], detected: Dict[str, Set[str]]) -> Dict[str, Any]:
    matched_expected: Set[Tuple[str, str]] = set()
    for func, exp_var in expected:
        for det_var in detected.get(func, set()):
            if var_matches(exp_var, det_var):
                matched_expected.add((func, exp_var))
                break

    detected_pairs = {(f, v) for f, vars_set in detected.items() for v in vars_set}
    extra: Set[Tuple[str, str]] = set()
    for f, v in detected_pairs:
        ok = False
        for ef, ev in expected:
            if f == ef and var_matches(ev, v):
                ok = True
                break
        if not ok:
            extra.add((f, v))

    tp = len(matched_expected)
    fp = len(extra)
    fn = len(expected) - tp
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / len(expected) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matched_expected": matched_expected,
    }


def evaluate_sanitizer(expected: Set[Tuple[str, int]], detected: Set[Tuple[str, int]], tolerance: int) -> Dict[str, Any]:
    matched_expected: Set[Tuple[str, int]] = set()
    for ef, el in expected:
        hit = False
        for df, dl in detected:
            if ef == df and abs(el - dl) <= tolerance:
                hit = True
                break
        if hit:
            matched_expected.add((ef, el))

    extra: Set[Tuple[str, int]] = set()
    for df, dl in detected:
        ok = False
        for ef, el in expected:
            if ef == df and abs(el - dl) <= tolerance:
                ok = True
                break
        if not ok:
            extra.add((df, dl))

    tp = len(matched_expected)
    fp = len(extra)
    fn = len(expected) - tp
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / len(expected) if expected else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matched_expected": matched_expected,
    }


def to4(v: float) -> float:
    return round(v, 4)


def main() -> int:
    ap = argparse.ArgumentParser(description="Compare taint/sanitizer recognition between current and baseline.")
    ap.add_argument(
        "--current",
        required=True,
        type=Path,
        help="Current conversations.jsonl path OR results dir OR model dir.",
    )
    ap.add_argument(
        "--baseline",
        type=Path,
        default=Path("/workspace/prompt_v1_output/gpt5-mini-bad-partitioning/gpt-5-mini-conversations.jsonl"),
        help="Baseline conversations.jsonl path or directory.",
    )
    ap.add_argument(
        "--labels-dir",
        type=Path,
        default=Path("/workspace/bad-partitioning-ta_groundtruth_labels/flow_labels/taint_sanitizer_labels"),
        help="Ground truth taint/sanitizer labels directory.",
    )
    ap.add_argument("--sanitizer-tolerance", type=int, default=2, help="Line tolerance for sanitizer matching.")
    ap.add_argument("--output-dir", type=Path, default=None, help="Output directory.")
    args = ap.parse_args()

    current_conv = resolve_conversations_path(args.current)
    baseline_conv = resolve_conversations_path(args.baseline)
    if not args.labels_dir.exists():
        raise FileNotFoundError(f"labels dir not found: {args.labels_dir}")

    out_dir = args.output_dir or (current_conv.parent / "compare_taint_sanitizer")
    out_dir.mkdir(parents=True, exist_ok=True)

    taint_expected = load_taint_expected(args.labels_dir)
    sanitizer_expected = load_sanitizer_expected(args.labels_dir)

    cur_taint, cur_san = collect_detected_from_conversations(current_conv)
    base_taint, base_san = collect_detected_from_conversations(baseline_conv)

    cur_t = evaluate_taint(taint_expected, cur_taint)
    base_t = evaluate_taint(taint_expected, base_taint)
    cur_s = evaluate_sanitizer(sanitizer_expected, cur_san, args.sanitizer_tolerance)
    base_s = evaluate_sanitizer(sanitizer_expected, base_san, args.sanitizer_tolerance)

    taint_delta = cur_t["f1"] - base_t["f1"]
    san_delta = cur_s["f1"] - base_s["f1"]

    def verdict(delta: float) -> str:
        if delta > 0:
            return "improved"
        if delta < 0:
            return "regressed"
        return "no_change"

    summary = {
        "current_conversations": str(current_conv),
        "baseline_conversations": str(baseline_conv),
        "labels_dir": str(args.labels_dir),
        "sanitizer_tolerance": args.sanitizer_tolerance,
        "verdict": {
            "taint": verdict(taint_delta),
            "sanitizer": verdict(san_delta),
        },
        "delta_f1": {
            "taint": to4(taint_delta),
            "sanitizer": to4(san_delta),
        },
        "current": {
            "taint": {
                "precision": to4(cur_t["precision"]),
                "recall": to4(cur_t["recall"]),
                "f1": to4(cur_t["f1"]),
                "tp": cur_t["tp"],
                "fp": cur_t["fp"],
                "fn": cur_t["fn"],
                "expected_count": len(taint_expected),
            },
            "sanitizer": {
                "precision": to4(cur_s["precision"]),
                "recall": to4(cur_s["recall"]),
                "f1": to4(cur_s["f1"]),
                "tp": cur_s["tp"],
                "fp": cur_s["fp"],
                "fn": cur_s["fn"],
                "expected_count": len(sanitizer_expected),
            },
        },
        "baseline": {
            "taint": {
                "precision": to4(base_t["precision"]),
                "recall": to4(base_t["recall"]),
                "f1": to4(base_t["f1"]),
                "tp": base_t["tp"],
                "fp": base_t["fp"],
                "fn": base_t["fn"],
                "expected_count": len(taint_expected),
            },
            "sanitizer": {
                "precision": to4(base_s["precision"]),
                "recall": to4(base_s["recall"]),
                "f1": to4(base_s["f1"]),
                "tp": base_s["tp"],
                "fp": base_s["fp"],
                "fn": base_s["fn"],
                "expected_count": len(sanitizer_expected),
            },
        },
    }

    summary_path = out_dir / "taint_sanitizer_summary.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    # expected labelごとの比較
    taint_rows = []
    for func, var in sorted(taint_expected):
        base_hit = (func, var) in base_t["matched_expected"]
        cur_hit = (func, var) in cur_t["matched_expected"]
        if cur_hit and not base_hit:
            status = "improved"
        elif base_hit and not cur_hit:
            status = "regressed"
        else:
            status = "no_change"
        taint_rows.append(
            {
                "function": func,
                "var": var,
                "baseline_hit": int(base_hit),
                "current_hit": int(cur_hit),
                "status": status,
            }
        )

    san_rows = []
    for func, line in sorted(sanitizer_expected):
        base_hit = (func, line) in base_s["matched_expected"]
        cur_hit = (func, line) in cur_s["matched_expected"]
        if cur_hit and not base_hit:
            status = "improved"
        elif base_hit and not cur_hit:
            status = "regressed"
        else:
            status = "no_change"
        san_rows.append(
            {
                "function": func,
                "line": line,
                "baseline_hit": int(base_hit),
                "current_hit": int(cur_hit),
                "status": status,
            }
        )

    taint_csv = out_dir / "taint_label_comparison.csv"
    with taint_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["function", "var", "baseline_hit", "current_hit", "status"])
        w.writeheader()
        w.writerows(taint_rows)

    san_csv = out_dir / "sanitizer_label_comparison.csv"
    with san_csv.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["function", "line", "baseline_hit", "current_hit", "status"])
        w.writeheader()
        w.writerows(san_rows)

    print("[compare_taint_sanitizers] Comparison finished")
    print(f"  current  : {current_conv}")
    print(f"  baseline : {baseline_conv}")
    print(f"  verdict  : taint={summary['verdict']['taint']}, sanitizer={summary['verdict']['sanitizer']}")
    print(f"  delta F1 : taint={summary['delta_f1']['taint']:+.4f}, sanitizer={summary['delta_f1']['sanitizer']:+.4f}")
    print(f"  outputs  : {summary_path}, {taint_csv}, {san_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

