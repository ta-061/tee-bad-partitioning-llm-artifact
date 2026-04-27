#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations
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
    "shared memory overwrite smo": "direct_usage_of_shared_memory",
    "direct_usage_of_shared_memory": "direct_usage_of_shared_memory",
    "direct usage of shared memory": "direct_usage_of_shared_memory",
    "direct usage of shared memory dus": "direct_usage_of_shared_memory",
}

CONVERSATION_FILENAMES = (
    "conversations.jsonl",
    "ta_conversations.jsonl",
    "conversations.json",
    "ta_conversations.json",
)

# Manual vulnerability-level integration rule.
# Source GT lines are canonicalized into target GT lines during prediction scoring.
# This is applied to both LLM and DITING predictions.
MANUAL_EQUIVALENT_GT_LINES = {
}


@dataclass(frozen=True, order=True)
class Pair:
    line: int
    category: str


def to4(value: float) -> float:
    return round(value, 4)


def jaccard_similarity(left: Set[Any], right: Set[Any]) -> float:
    if not left and not right:
        return 1.0
    union = left | right
    if not union:
        return 0.0
    return len(left & right) / len(union)


def summarize_pairwise_jaccard(run_sets: List[Set[Any]]) -> Dict[str, Any]:
    if len(run_sets) < 2:
        return {
            "mean": 1.0,
            "min": 1.0,
            "max": 1.0,
            "pair_count": 0,
        }

    scores = [jaccard_similarity(left, right) for left, right in combinations(run_sets, 2)]
    return {
        "mean": to4(sum(scores) / len(scores)),
        "min": to4(min(scores)),
        "max": to4(max(scores)),
        "pair_count": len(scores),
    }


def summarize_line_jaccard(run_lines: List[Set[int]]) -> Dict[str, Any]:
    return summarize_pairwise_jaccard(run_lines)


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


def normalize_category(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    raw_key = value.strip().lower()
    # Accept labels like "Input Validation Weakness (IVW)"
    raw_key = re.sub(r"\s*\([^)]*\)\s*$", "", raw_key).strip()
    normalized_key = re.sub(r"[\s\-]+", "_", raw_key)
    normalized_key = re.sub(r"_+", "_", normalized_key).strip("_")
    mapped = CATEGORY_ALIASES.get(raw_key) or CATEGORY_ALIASES.get(normalized_key) or normalized_key
    return mapped if mapped in GT_CATEGORIES else None


def extract_lines(value: Any) -> List[int]:
    lines: Set[int] = set()

    def _walk(v: Any):
        if isinstance(v, list):
            for item in v:
                _walk(item)
            return
        if isinstance(v, str) and "," in v:
            for part in v.split(","):
                _walk(part)
            return
        num = parse_int(v)
        if num is not None:
            lines.add(num)

    _walk(value)
    return sorted(lines)


def iter_categories(entry: Dict[str, Any]) -> Iterable[str]:
    for rid in entry.get("categories", []) or []:
        cat = normalize_category(rid)
        if cat:
            yield cat

    for rid in entry.get("rule_ids", []) or []:
        cat = normalize_category(rid)
        if cat:
            yield cat

    for rid in entry.get("rules", []) or []:
        cat = normalize_category(rid)
        if cat:
            yield cat

    cat = normalize_category(entry.get("primary_rule"))
    if cat:
        yield cat

    cat = normalize_category(entry.get("primary_rule_id"))
    if cat:
        yield cat

    distribution = entry.get("rule_distribution")
    if isinstance(distribution, dict):
        for rid in distribution.keys():
            cat = normalize_category(rid)
            if cat:
                yield cat


def load_json(path: Path) -> Dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _sort_results_dir_key(path: Path) -> int:
    m = re.match(r"results_(\d+)$", path.name)
    if not m:
        return -1
    return int(m.group(1))


def resolve_vulnerabilities_path(path: Path) -> Path:
    if path.is_file():
        return path

    direct = path / "ta_vulnerabilities.json"
    if direct.exists():
        return direct

    candidates: List[Tuple[int, Path]] = []
    for d in path.glob("results_*"):
        if not d.is_dir():
            continue
        idx = _sort_results_dir_key(d)
        if idx < 0:
            continue
        candidate = d / "ta_vulnerabilities.json"
        if candidate.exists():
            candidates.append((idx, candidate))
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    typo_direct = path / "ta_vulnerabilies.json"
    if typo_direct.exists():
        return typo_direct

    raise FileNotFoundError(f"ta_vulnerabilities.json not found under: {path}")


def resolve_conversations_path(path: Path) -> Path:
    if path.is_file():
        return path

    for name in CONVERSATION_FILENAMES:
        direct = path / name
        if direct.exists():
            return direct

    candidates: List[Tuple[int, Path]] = []
    for d in path.glob("results_*"):
        if not d.is_dir():
            continue
        idx = _sort_results_dir_key(d)
        if idx < 0:
            continue
        for name in CONVERSATION_FILENAMES:
            candidate = d / name
            if candidate.exists():
                candidates.append((idx, candidate))
                break
    if candidates:
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    names = ", ".join(CONVERSATION_FILENAMES)
    raise FileNotFoundError(f"No conversation file ({names}) found under: {path}")


def find_results_dirs(model_root: Path) -> List[Tuple[int, Path]]:
    dirs: List[Tuple[int, Path]] = []
    for d in model_root.glob("results_*"):
        if not d.is_dir():
            continue
        idx = _sort_results_dir_key(d)
        if idx < 0:
            continue
        has_vuln = (d / "ta_vulnerabilities.json").exists()
        has_conv = any((d / name).exists() for name in CONVERSATION_FILENAMES)
        if has_vuln and has_conv:
            dirs.append((idx, d))
    dirs.sort(key=lambda x: x[0])
    return dirs


def resolve_results_dir(path: Path) -> Path:
    if path.is_file():
        return path.parent

    if (path / "ta_candidate_flows.json").exists() or (path / "ta_vulnerabilities.json").exists():
        return path

    candidates = find_results_dirs(path)
    if candidates:
        return candidates[-1][1]

    raise FileNotFoundError(f"results directory not found under: {path}")


def infer_phase3_profile(results_dir: Path, sink_rule_ids: Set[str]) -> Tuple[str, str]:
    parts = [part.lower() for part in results_dir.parts]
    joined = "/".join(parts)
    token_set: Set[str] = set()
    for part in parts:
        token_set.update(token for token in re.split(r"[^a-z0-9]+", part) if token)

    # Prefer explicit experiment/model naming over sink contents. Mixed sink rule
    # sets can appear in write-only experiments, so rule_ids alone are not stable.
    if "general_sink_screening" in joined or "general" in token_set:
        return "general", "path_hint"

    # e12 is the named experiment for general sink screening, but the 5-run
    # evaluation directories are shortened to /.../ta/e12/<model>/results_N.
    if "e12" in token_set:
        return "general", "path_hint"

    if any(re.fullmatch(r"e\d+[a-z]?", token) for token in token_set):
        return "write-only", "path_hint"

    if "other" in sink_rule_ids:
        return "general", "sink_rules"
    if sink_rule_ids:
        return "write-only", "sink_rules"
    return "unknown", "unavailable"


def summarize_candidate_flow_coverage(
    results_dir: Path,
    gt_meta: Dict[Pair, Dict[str, str]],
) -> Dict[str, Any]:
    candidate_flows_path = results_dir / "ta_candidate_flows.json"
    sinks_path = results_dir / "ta_sinks.json"

    line_to_meta: Dict[int, Dict[str, str]] = {}
    function_to_lines: Dict[str, Set[int]] = defaultdict(set)
    for pair, meta in gt_meta.items():
        line_to_meta.setdefault(pair.line, meta)
        function_name = (meta.get("function") or "").strip()
        if function_name:
            function_to_lines[function_name].add(pair.line)

    gt_lines = set(line_to_meta.keys())
    gt_functions = set(function_to_lines.keys())

    chain_functions: Set[str] = set()
    chain_count = 0
    missing_artifacts: List[str] = []

    if candidate_flows_path.exists():
        raw_flows = json.loads(candidate_flows_path.read_text(encoding="utf-8"))
        if isinstance(raw_flows, list):
            chain_count = len(raw_flows)
            for flow in raw_flows:
                if not isinstance(flow, dict):
                    continue
                chain = flow.get("chains", {})
                if not isinstance(chain, dict):
                    continue
                function_chain = chain.get("function_chain", [])
                if not isinstance(function_chain, list):
                    continue
                for item in function_chain:
                    if isinstance(item, str) and item.strip():
                        chain_functions.add(item.strip())
        else:
            missing_artifacts.append("ta_candidate_flows.json (not a list)")
    else:
        missing_artifacts.append("ta_candidate_flows.json")

    analysis_mode = None
    sink_count = 0
    phase3_profile = "unknown"
    phase3_profile_source = "unavailable"
    if sinks_path.exists():
        raw_sinks = json.loads(sinks_path.read_text(encoding="utf-8"))
        if isinstance(raw_sinks, dict):
            analysis_mode = raw_sinks.get("analysis_mode")
            sinks = raw_sinks.get("sinks", [])
            if isinstance(sinks, list):
                sink_count = len(sinks)
                sink_rule_ids = {
                    str(item.get("rule_id")).strip().lower()
                    for item in sinks
                    if isinstance(item, dict) and item.get("rule_id") is not None
                }
                phase3_profile, phase3_profile_source = infer_phase3_profile(results_dir, sink_rule_ids)
            else:
                missing_artifacts.append("ta_sinks.json (sinks is not a list)")
                phase3_profile_source = "invalid_sinks_json"
        else:
            missing_artifacts.append("ta_sinks.json (not a dict)")
            phase3_profile_source = "invalid_sinks_json"
    else:
        missing_artifacts.append("ta_sinks.json")
        phase3_profile_source = "missing_sinks_json"

    coverage_basis = (
        "function_chain_proxy: if a ground-truth function appears in any candidate "
        "flow chain, all GT lines for that function are counted as covered"
    )

    covered_functions = sorted(chain_functions & gt_functions)
    uncovered_functions = sorted(gt_functions - set(covered_functions))

    covered_gt_lines: Set[int] = set()
    for function_name in covered_functions:
        covered_gt_lines.update(function_to_lines.get(function_name, set()))
    uncovered_gt_lines = sorted(gt_lines - covered_gt_lines)

    coverage_percent = (len(covered_gt_lines) / len(gt_lines) * 100.0) if gt_lines else 0.0

    return {
        "results_dir": str(results_dir),
        "candidate_flows_json": str(candidate_flows_path),
        "sinks_json": str(sinks_path),
        "available": candidate_flows_path.exists(),
        "missing_artifacts": missing_artifacts,
        "analysis_mode": analysis_mode,
        "phase3_profile_inferred": phase3_profile,
        "phase3_profile_source": phase3_profile_source,
        "sink_count": sink_count,
        "chain_count": chain_count,
        "coverage_available": candidate_flows_path.exists(),
        "coverage_basis": coverage_basis,
        "gt_total_line_count": len(gt_lines),
        "gt_total_function_count": len(gt_functions),
        "covered_gt_line_count": len(covered_gt_lines),
        "uncovered_gt_line_count": len(uncovered_gt_lines),
        "covered_gt_function_count": len(covered_functions),
        "uncovered_gt_function_count": len(uncovered_functions),
        "coverage_percent": to4(coverage_percent),
        "covered_gt_lines": sorted(covered_gt_lines),
        "uncovered_gt_lines": uncovered_gt_lines,
        "covered_functions": covered_functions,
        "uncovered_functions": uncovered_functions,
    }


def load_ground_truth_pairs(csv_path: Path) -> Tuple[Set[Pair], Dict[Pair, Dict[str, str]], Dict[int, Set[str]]]:
    gt_pairs: Set[Pair] = set()
    gt_meta: Dict[Pair, Dict[str, str]] = {}
    line_to_categories: Dict[int, Set[str]] = defaultdict(set)

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            line = parse_int(row.get("Line Number"))
            category = normalize_category(row.get("Category"))
            if line is None or category is None:
                continue
            pair = Pair(line, category)
            gt_pairs.add(pair)
            line_to_categories[line].add(category)
            if pair not in gt_meta:
                gt_meta[pair] = {
                    "function": row.get("Function", ""),
                    "label_id": row.get("Label ID", ""),
                    "group": row.get("Group", ""),
                    "category_jp": row.get("Category_JP", ""),
                }

    return gt_pairs, gt_meta, line_to_categories


def load_partial_match_map(
    partial_csv_path: Optional[Path],
    gt_line_to_categories: Dict[int, Set[str]],
) -> Dict[int, Set[Pair]]:
    partial_map: Dict[int, Set[Pair]] = defaultdict(set)
    if partial_csv_path is None or not partial_csv_path.exists():
        return partial_map

    with partial_csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            det_line = parse_int(row.get("Detected Line"))
            gt_line = parse_int(row.get("Related Ground Truth Line"))
            if det_line is None or gt_line is None:
                continue
            categories = gt_line_to_categories.get(gt_line, set())
            for category in categories:
                partial_map[det_line].add(Pair(gt_line, category))
    return partial_map


def build_group_canonical_pair_map(
    gt_meta: Dict[Pair, Dict[str, str]],
) -> Dict[Pair, Pair]:
    canonical_map: Dict[Pair, Pair] = {}
    for src_line, dst_line in MANUAL_EQUIVALENT_GT_LINES.items():
        for category in GT_CATEGORIES:
            src_pair = Pair(src_line, category)
            dst_pair = Pair(dst_line, category)
            if src_pair in gt_meta and dst_pair in gt_meta:
                canonical_map[src_pair] = dst_pair
    return canonical_map


def apply_group_canonical_map(
    pred_pairs: Set[Pair],
    pred_lines: Set[int],
    canonical_pair_map: Optional[Dict[Pair, Pair]] = None,
) -> Tuple[Set[Pair], Set[int]]:
    if not canonical_pair_map:
        return set(pred_pairs), set(pred_lines)

    collapsed_pairs = {canonical_pair_map.get(pair, pair) for pair in pred_pairs}

    # Line-level predictions may not carry categories (e.g., "other" only). Map
    # the line only when all group mappings agree on the same canonical line.
    line_candidates: Dict[int, Set[int]] = defaultdict(set)
    for src_pair, dst_pair in canonical_pair_map.items():
        line_candidates[src_pair.line].add(dst_pair.line)
    line_map = {line: next(iter(dsts)) for line, dsts in line_candidates.items() if len(dsts) == 1}

    collapsed_lines = {line_map.get(line, line) for line in pred_lines}
    collapsed_lines |= {pair.line for pair in collapsed_pairs}
    return collapsed_pairs, collapsed_lines


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


def _canonical_lines_from_prediction(
    line: int,
    partial_map: Dict[int, Set[Pair]],
) -> Set[int]:
    mapped = partial_map.get(line, set())
    mapped_lines = {pair.line for pair in mapped}
    if mapped_lines:
        return mapped_lines
    return {line}


def _iter_vulnerability_entries(data: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    merged_by_line = data.get("merged_by_line")
    if isinstance(merged_by_line, dict):
        for line_key, raw_entry in merged_by_line.items():
            if not isinstance(raw_entry, dict):
                continue
            entry = dict(raw_entry)

            if "line" not in entry:
                parsed_line = parse_int(line_key)
                if parsed_line is not None:
                    entry["line"] = parsed_line

            categories = entry.get("categories")
            if isinstance(categories, list):
                # Keep backward compatibility with downstream extraction logic.
                entry.setdefault("rules", categories)
                entry.setdefault("rule_ids", categories)

            yield entry
        return

    vulnerabilities = data.get("vulnerabilities", []) or []
    structural_risks = data.get("structural_risks", []) or []
    for entry in list(vulnerabilities) + list(structural_risks):
        if isinstance(entry, dict):
            yield entry


def extract_pairs_from_vulnerability_json(
    data: Dict[str, Any],
    partial_map: Optional[Dict[int, Set[Pair]]] = None,
) -> Set[Pair]:
    pairs: Set[Pair] = set()
    partial_map = partial_map or {}

    for entry in _iter_vulnerability_entries(data):
        lines = extract_lines(entry.get("line"))
        if not lines:
            continue
        categories = set(iter_categories(entry))
        if not categories:
            continue
        for line in lines:
            for category in categories:
                pairs.update(_canonical_pairs_from_prediction(line, category, partial_map))
    return pairs


def extract_lines_from_vulnerability_json_all(
    data: Dict[str, Any],
    partial_map: Optional[Dict[int, Set[Pair]]] = None,
) -> Set[int]:
    pred_lines: Set[int] = set()
    partial_map = partial_map or {}

    for entry in _iter_vulnerability_entries(data):
        lines = extract_lines(entry.get("line"))
        if not lines:
            continue
        for line in lines:
            pred_lines.update(_canonical_lines_from_prediction(line, partial_map))
    return pred_lines


def metrics(pred: Set[Pair], gt: Set[Pair]) -> Dict[str, Any]:
    tp = pred & gt
    fp = pred - gt
    fn = gt - pred
    precision = len(tp) / len(pred) if pred else 0.0
    recall = len(tp) / len(gt) if gt else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "tp_set": tp,
        "fp_set": fp,
        "fn_set": fn,
        "tp": len(tp),
        "fp": len(fp),
        "fn": len(fn),
        "pred_count": len(pred),
        "gt_count": len(gt),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def line_metrics_from_lines(pred_lines: Set[int], gt: Set[Pair]) -> Dict[str, Any]:
    gt_lines = {item.line for item in gt}
    tp = pred_lines & gt_lines
    fp = pred_lines - gt_lines
    fn = gt_lines - pred_lines
    precision = len(tp) / len(pred_lines) if pred_lines else 0.0
    recall = len(tp) / len(gt_lines) if gt_lines else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "tp_set": tp,
        "fp_set": fp,
        "fn_set": fn,
        "tp": len(tp),
        "fp": len(fp),
        "fn": len(fn),
        "pred_count": len(pred_lines),
        "gt_count": len(gt_lines),
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def line_category_set_metrics(
    pred_lines: Set[int],
    pred_pairs: Set[Pair],
    gt_line_to_categories: Dict[int, Set[str]],
) -> Dict[str, Any]:
    pred_line_to_categories: Dict[int, Set[str]] = defaultdict(set)
    for pair in pred_pairs:
        pred_line_to_categories[pair.line].add(pair.category)

    gt_lines = set(gt_line_to_categories.keys())
    tp: Set[int] = set()
    fp: Set[int] = set()
    fn: Set[int] = set()

    for line in pred_lines:
        pred_categories = pred_line_to_categories.get(line, set())
        gt_categories = gt_line_to_categories.get(line, set())
        if line in gt_lines and (pred_categories & gt_categories):
            tp.add(line)
        else:
            fp.add(line)

    for line in gt_lines:
        pred_categories = pred_line_to_categories.get(line, set())
        gt_categories = gt_line_to_categories.get(line, set())
        if not (line in pred_lines and (pred_categories & gt_categories)):
            fn.add(line)

    precision = len(tp) / len(pred_lines) if pred_lines else 0.0
    recall = len(tp) / len(gt_lines) if gt_lines else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0
    return {
        "tp_set": tp,
        "fp_set": fp,
        "fn_set": fn,
        "tp": len(tp),
        "fp": len(fp),
        "fn": len(fn),
        "pred_count": len(pred_lines),
        "gt_count": len(gt_lines),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "pred_line_to_categories": dict(pred_line_to_categories),
    }


def line_metrics(pred: Set[Pair], gt: Set[Pair]) -> Dict[str, Any]:
    pred_lines = {item.line for item in pred}
    return line_metrics_from_lines(pred_lines, gt)


def per_category_metrics(pred: Set[Pair], gt: Set[Pair]) -> Dict[str, Dict[str, Any]]:
    result: Dict[str, Dict[str, Any]] = {}
    for category in sorted(GT_CATEGORIES):
        pred_c = {pair for pair in pred if pair.category == category}
        gt_c = {pair for pair in gt if pair.category == category}
        result[category] = metrics(pred_c, gt_c)
    return result


def build_vulnerability_eval(
    vulnerability_json_path: Path,
    gt_pairs: Set[Pair],
    partial_map: Optional[Dict[int, Set[Pair]]] = None,
    canonical_pair_map: Optional[Dict[Pair, Pair]] = None,
) -> Dict[str, Any]:
    data = load_json(vulnerability_json_path)
    pred_pairs = extract_pairs_from_vulnerability_json(data, partial_map=partial_map)
    pred_lines_all = extract_lines_from_vulnerability_json_all(data, partial_map=partial_map)
    pred_pairs, pred_lines_all = apply_group_canonical_map(pred_pairs, pred_lines_all, canonical_pair_map)
    gt_line_to_categories: Dict[int, Set[str]] = defaultdict(set)
    for pair in gt_pairs:
        gt_line_to_categories[pair.line].add(pair.category)
    strict_result = line_category_set_metrics(pred_lines_all, pred_pairs, dict(gt_line_to_categories))
    pair_result = metrics(pred_pairs, gt_pairs)
    line_result = line_metrics_from_lines(pred_lines_all, gt_pairs)
    category_result = per_category_metrics(pred_pairs, gt_pairs)
    return {
        "json_path": str(vulnerability_json_path),
        "pred_pairs": pred_pairs,
        "pred_lines_all": pred_lines_all,
        "strict_metrics": strict_result,
        "pair_metrics": pair_result,
        "line_metrics": line_result,
        "category_metrics": category_result,
    }


def normalize_var_name(value: str) -> str:
    value = value.strip()
    value = re.sub(r"\[\d+\.\.\d+\]", "[*]", value)
    value = re.sub(r"\[\d+\]", "[*]", value)
    return value


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

    stripped = text.strip()
    stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
    stripped = re.sub(r"\s*```$", "", stripped)

    try:
        obj = json.loads(stripped)
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        obj = json.loads(match.group(0))
        if isinstance(obj, dict):
            return obj
    except json.JSONDecodeError:
        return None
    return None


def parse_site_line(site: Any) -> Optional[int]:
    if not isinstance(site, str):
        return None
    return parse_int(site.split(":")[-1] if ":" in site else site)


def iter_sanitizers(payload: Dict[str, Any]) -> Iterable[Dict[str, Any]]:
    taint_analysis = payload.get("taint_analysis")
    if isinstance(taint_analysis, dict):
        for sanitizer in taint_analysis.get("sanitizers", []) or []:
            if isinstance(sanitizer, dict):
                yield sanitizer

    for key in ("sanitizers", "effective_sanitizers"):
        for sanitizer in payload.get(key, []) or []:
            if isinstance(sanitizer, dict):
                yield sanitizer


def _iter_flow_conversation_objects(conversations_path: Path) -> Iterable[Dict[str, Any]]:
    suffix = conversations_path.suffix.lower()

    if suffix == ".jsonl":
        with conversations_path.open("r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(obj, dict) and obj.get("type") == "flow_conversations":
                    yield obj
        return

    with conversations_path.open("r", encoding="utf-8", errors="ignore") as f:
        try:
            root = json.load(f)
        except json.JSONDecodeError:
            return

    queue: List[Any] = [root]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            if current.get("type") == "flow_conversations":
                yield current
            for key in ("records", "items", "data", "entries", "logs"):
                value = current.get(key)
                if isinstance(value, list):
                    queue.extend(value)
        elif isinstance(current, list):
            queue.extend(current)


def collect_detected_from_conversations(
    conversations_path: Path,
) -> Tuple[Dict[str, Set[str]], Set[Tuple[str, int]]]:
    per_function_taints: Dict[str, Set[str]] = {}
    sanitizer_locations: Set[Tuple[str, int]] = set()

    for obj in _iter_flow_conversation_objects(conversations_path):
        for conv in obj.get("conversations", []) or []:
            if not isinstance(conv, dict):
                continue
            payload = extract_json_payload(conv.get("response"))
            if not payload:
                continue

            function_name = (
                (payload.get("taint_analysis") or {}).get("function")
                or payload.get("function")
                or conv.get("function")
                or "unknown"
            )
            if function_name not in per_function_taints:
                per_function_taints[function_name] = set()

            taint_analysis = payload.get("taint_analysis")
            tainted_vars = []
            if isinstance(taint_analysis, dict):
                tainted_vars = taint_analysis.get("tainted_vars", []) or []
            if not tainted_vars:
                tainted_vars = payload.get("tainted_vars", []) or []

            for tainted_var in tainted_vars:
                if isinstance(tainted_var, dict):
                    tainted_var = (
                        tainted_var.get("name")
                        or tainted_var.get("variable")
                        or tainted_var.get("var")
                        or str(tainted_var)
                    )
                if not isinstance(tainted_var, str):
                    tainted_var = str(tainted_var)
                per_function_taints[function_name].add(normalize_var_name(tainted_var))

            for sanitizer in iter_sanitizers(payload):
                location = sanitizer.get("location", "")
                if isinstance(location, str) and ":" in location:
                    parts = location.split(":")
                    san_func = parts[0] or function_name
                    san_line = parse_int(parts[1]) if len(parts) > 1 else None
                    if san_line is not None:
                        sanitizer_locations.add((san_func, san_line))
                        continue

                site_line = parse_site_line(sanitizer.get("site", ""))
                if site_line is not None:
                    sanitizer_locations.add((function_name, site_line))

    return per_function_taints, sanitizer_locations


def load_taint_expected(labels_dir: Path) -> Set[Tuple[str, str]]:
    expected: Set[Tuple[str, str]] = set()
    for path in sorted(labels_dir.glob("*_taint_labels.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                function_name = (row.get("function") or "").strip()
                var_field = (row.get("var") or "").strip()
                if not function_name or not var_field:
                    continue
                for part in [item.strip() for item in var_field.split(",") if item.strip()]:
                    expected.add((function_name, normalize_var_name(part)))
    return expected


def load_sanitizer_expected(labels_dir: Path) -> Set[Tuple[str, int]]:
    expected: Set[Tuple[str, int]] = set()
    for path in sorted(labels_dir.glob("*_sanitizer_labels.csv")):
        with path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                function_name = (row.get("function") or "").strip()
                line = parse_int(row.get("line"))
                if function_name and line is not None:
                    expected.add((function_name, line))
    return expected


def evaluate_taint(
    expected: Set[Tuple[str, str]],
    detected: Dict[str, Set[str]],
) -> Dict[str, Any]:
    matched_expected: Set[Tuple[str, str]] = set()
    for function_name, expected_var in expected:
        for detected_var in detected.get(function_name, set()):
            if var_matches(expected_var, detected_var):
                matched_expected.add((function_name, expected_var))
                break

    detected_pairs = {(function_name, var) for function_name, vars_set in detected.items() for var in vars_set}

    extra: Set[Tuple[str, str]] = set()
    for function_name, detected_var in detected_pairs:
        is_extra = True
        for expected_function, expected_var in expected:
            if function_name == expected_function and var_matches(expected_var, detected_var):
                is_extra = False
                break
        if is_extra:
            extra.add((function_name, detected_var))

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
        "expected_count": len(expected),
        "matched_expected": matched_expected,
        "extra": extra,
        "detected_pairs": detected_pairs,
    }


def evaluate_sanitizer(
    expected: Set[Tuple[str, int]],
    detected: Set[Tuple[str, int]],
    tolerance: int = 2,
) -> Dict[str, Any]:
    matched_expected: Set[Tuple[str, int]] = set()

    for expected_function, expected_line in expected:
        hit = False
        for detected_function, detected_line in detected:
            if expected_function == detected_function and abs(expected_line - detected_line) <= tolerance:
                hit = True
                break
        if hit:
            matched_expected.add((expected_function, expected_line))

    extra: Set[Tuple[str, int]] = set()
    for detected_function, detected_line in detected:
        is_extra = True
        for expected_function, expected_line in expected:
            if expected_function == detected_function and abs(expected_line - detected_line) <= tolerance:
                is_extra = False
                break
        if is_extra:
            extra.add((detected_function, detected_line))

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
        "expected_count": len(expected),
        "matched_expected": matched_expected,
        "extra": extra,
        "detected_set": detected,
    }


def build_taint_sanitizer_eval(
    conversations_jsonl_path: Path,
    labels_dir: Path,
    sanitizer_tolerance: int = 2,
) -> Dict[str, Any]:
    taint_expected = load_taint_expected(labels_dir)
    sanitizer_expected = load_sanitizer_expected(labels_dir)
    detected_taints, detected_sanitizers = collect_detected_from_conversations(conversations_jsonl_path)
    taint_result = evaluate_taint(taint_expected, detected_taints)
    sanitizer_result = evaluate_sanitizer(sanitizer_expected, detected_sanitizers, tolerance=sanitizer_tolerance)
    return {
        "conversations_path": str(conversations_jsonl_path),
        "taint_expected": taint_expected,
        "sanitizer_expected": sanitizer_expected,
        "detected_taints": detected_taints,
        "detected_sanitizers": detected_sanitizers,
        "taint_metrics": taint_result,
        "sanitizer_metrics": sanitizer_result,
    }


def build_consensus_pairs(run_pairs: List[Set[Pair]], min_votes: int) -> Tuple[Set[Pair], Dict[Pair, int]]:
    votes: Dict[Pair, int] = defaultdict(int)
    for pred_pairs in run_pairs:
        for pair in pred_pairs:
            votes[pair] += 1
    consensus = {pair for pair, count in votes.items() if count >= min_votes}
    return consensus, dict(votes)


def build_consensus_lines(run_lines: List[Set[int]], min_votes: int) -> Tuple[Set[int], Dict[int, int]]:
    votes: Dict[int, int] = defaultdict(int)
    for pred_lines in run_lines:
        for line in pred_lines:
            votes[line] += 1
    consensus = {line for line, count in votes.items() if count >= min_votes}
    return consensus, dict(votes)


def build_consensus_taints(
    detected_taints_per_run: List[Dict[str, Set[str]]],
    min_votes: int,
) -> Dict[str, Set[str]]:
    votes: Dict[Tuple[str, str], int] = defaultdict(int)
    for per_function in detected_taints_per_run:
        seen_in_run: Set[Tuple[str, str]] = set()
        for function_name, vars_set in per_function.items():
            for var in vars_set:
                seen_in_run.add((function_name, var))
        for key in seen_in_run:
            votes[key] += 1

    consensus: Dict[str, Set[str]] = defaultdict(set)
    for (function_name, var), count in votes.items():
        if count >= min_votes:
            consensus[function_name].add(var)
    return dict(consensus)


def build_consensus_sanitizers(
    detected_sanitizers_per_run: List[Set[Tuple[str, int]]],
    min_votes: int,
) -> Set[Tuple[str, int]]:
    votes: Dict[Tuple[str, int], int] = defaultdict(int)
    for detected_set in detected_sanitizers_per_run:
        for item in detected_set:
            votes[item] += 1
    return {item for item, count in votes.items() if count >= min_votes}


def delta_verdict(delta: float) -> str:
    if delta > 0:
        return "improved"
    if delta < 0:
        return "regressed"
    return "no_change"


def write_csv(path: Path, fieldnames: List[str], rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
