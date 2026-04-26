#!/usr/bin/env python3
"""Regenerate paper-facing tables from the released JSON/CSV artifacts.

The script uses only Python's standard library.  It reads the curated
evaluation data under ``data/`` and writes CSV/Markdown tables under
``results/tables/``.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ACTUAL_DIR = ROOT / "data" / "actual_evaluation" / "e12_5runs"
PROMPT_DIR = ROOT / "data" / "prompt_ablation" / "experiments"
OUT_DIR = ROOT / "results" / "tables"

CAT_KEYS = {
    "UDO": "unencrypted_data_output",
    "IVW": "input_validation_weakness",
    "DUS": "direct_usage_of_shared_memory",
}

MODEL_ORDER = [
    "gpt-5-mini-2025-08-07",
    "gpt-5.2-2025-12-11",
    "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001",
    "deepseek-chat",
    "gemini-3.1-pro",
    "qwen3.5-27b",
    "gemma-3-27b-it",
    "gemma-4-31b-it",
]

MODEL_LABELS = {
    "gpt-5-mini-2025-08-07": "GPT-5-mini",
    "gpt-5.2-2025-12-11": "GPT-5.2",
    "claude-sonnet-4-5-20250929": "Claude Sonnet 4.5",
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
    "deepseek-chat": "DeepSeek V3.2",
    "gemini-3.1-pro": "Gemini 3.1 Pro",
    "qwen3.5-27b": "Qwen3.5-27B",
    "gemma-3-27b-it": "gemma-3-27b-it",
    "gemma-4-31b-it": "gemma-4-31B-it",
}

PROMPT_ROWS = [
    (
        "e03",
        "e03_line_grouped_end",
        "END candidate review scheme",
    ),
    (
        "e09c",
        "e09c_call_forwarding_plus_recal",
        "Candidate-generation policy including suppression of judgment based only on arguments",
    ),
    (
        "e10",
        "e10_modular_framework",
        "Introduction of the domain adapter into Phase 5",
    ),
    (
        "e11",
        "e11_streamlined_framework",
        "Explicit enumeration of shared-memory operations",
    ),
    (
        "e12",
        "e12_general_sink_screening",
        "Revision of the Phase 3 candidate-screening criteria",
    ),
]


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def fmt(value, digits: int = 3) -> str:
    if value is None:
        return "---"
    if isinstance(value, int):
        return str(value)
    return f"{float(value):.{digits}f}"


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def actual_summary(model_dir: str) -> dict:
    return load_json(ACTUAL_DIR / model_dir / "summary.json")


def actual_metric(summary: dict) -> dict:
    return summary["target_scores"]["vulnerability_all"]["strict_line_category"]


def actual_cat(summary: dict, short_name: str) -> dict:
    return summary["target_scores"]["vulnerability_by_category"][CAT_KEYS[short_name]]


def latest_coverage(summary: dict) -> dict:
    coverage = summary.get("coverage", {})
    if coverage.get("results"):
        return coverage["results"][-1]
    if coverage.get("latest_run"):
        return coverage["latest_run"]
    return coverage


def generate_actual_tables() -> tuple[list[dict], list[dict], list[dict]]:
    model_rows: list[dict] = []
    category_rows: list[dict] = []
    coverage_rows: list[dict] = []

    first_summary = actual_summary(MODEL_ORDER[0])
    diting = first_summary["diting_complementarity"]["diting_only"]["strict_line_category"]
    model_rows.append(
        {
            "model": "DITING",
            "f1": fmt(diting["f1"]),
            "precision": fmt(diting["precision"]),
            "catprec": "---",
            "tp": diting["tp"],
            "fp": diting["fp"],
            "union_f1": "---",
            "union_recall": "---",
            "llm_only_tp": "---",
            "diting_only_tp": "---",
        }
    )

    for model_dir in MODEL_ORDER:
        summary = actual_summary(model_dir)
        metric = actual_metric(summary)
        comp = summary["diting_complementarity"]
        union = comp["combined_union"]["strict_line_category"]
        overlap = comp["overlap_on_ground_truth"]["strict_line_category"]
        catprec = summary["target_scores"]["vulnerability_all"]["line_hit_category_precision"]["value"]
        model_rows.append(
            {
                "model": MODEL_LABELS.get(model_dir, model_dir),
                "f1": fmt(metric["f1"]),
                "precision": fmt(metric["precision"]),
                "catprec": fmt(catprec),
                "tp": metric["tp"],
                "fp": metric["fp"],
                "union_f1": fmt(union["f1"]),
                "union_recall": fmt(union["recall"]),
                "llm_only_tp": overlap["llm_only_count"],
                "diting_only_tp": overlap["diting_only_count"],
            }
        )

        cat_row = {"model": MODEL_LABELS.get(model_dir, model_dir)}
        for short in ("UDO", "IVW", "DUS"):
            block = actual_cat(summary, short)
            cat_row[f"{short.lower()}_f1"] = fmt(block["f1"], 4)
            cat_row[f"{short.lower()}_precision"] = fmt(block["precision"], 4)
            cat_row[f"{short.lower()}_recall"] = fmt(block["recall"], 4)
            cat_row[f"{short.lower()}_tp"] = block["tp"]
            cat_row[f"{short.lower()}_fp"] = block["fp"]
            cat_row[f"{short.lower()}_fn"] = block["fn"]
        category_rows.append(cat_row)

        cov = latest_coverage(summary)
        coverage_rows.append(
            {
                "model": MODEL_LABELS.get(model_dir, model_dir),
                "phase3_profile": cov.get("phase3_profile_inferred"),
                "sinks": cov.get("sink_count"),
                "chains": cov.get("chain_count"),
                "gt_lines": cov.get("gt_total_line_count"),
                "covered": cov.get("covered_gt_line_count"),
                "uncovered": cov.get("uncovered_gt_line_count"),
                "coverage_percent": fmt(cov.get("coverage_percent"), 1),
                "uncovered_lines": cov.get("uncovered_gt_lines", ""),
                "uncovered_functions": cov.get("uncovered_functions", ""),
            }
        )

    return model_rows, category_rows, coverage_rows


def generate_prompt_table() -> list[dict]:
    rows: list[dict] = []
    for version, dirname, description in PROMPT_ROWS:
        summary = load_json(PROMPT_DIR / dirname / "summary.json")
        metric = summary["current_metrics"]["vulnerability_all"]["strict_line_category"]
        dus = summary["current_metrics"]["vulnerability_by_category"][CAT_KEYS["DUS"]]
        coverage = summary.get("coverage", {})
        rows.append(
            {
                "version": version,
                "main_change": description,
                "f1": fmt(metric["f1"]),
                "dus_f1": fmt(dus["f1"]),
                "dus_tp": dus["tp"],
                "candidate_coverage": fmt(coverage.get("coverage_percent"), 1),
            }
        )
    return rows


def markdown_table(rows: list[dict], headers: list[tuple[str, str]]) -> list[str]:
    labels = [label for _, label in headers]
    keys = [key for key, _ in headers]
    lines = [
        "| " + " | ".join(labels) + " |",
        "| " + " | ".join("---" for _ in labels) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(key, "")) for key in keys) + " |")
    return lines


def write_markdown(model_rows: list[dict], prompt_rows: list[dict]) -> None:
    lines: list[str] = [
        "# Regenerated Paper Tables",
        "",
        "Generated by `scripts/generate_paper_tables.py` from the released artifact data.",
        "",
        "## Main Metrics and Union Results with DITING",
        "",
    ]
    lines.extend(
        markdown_table(
            model_rows,
            [
                ("model", "Model"),
                ("f1", "F1"),
                ("precision", "Precision"),
                ("catprec", "CatPrec"),
                ("tp", "TP"),
                ("fp", "FP"),
                ("union_f1", "Union F1"),
                ("union_recall", "Union Recall"),
                ("llm_only_tp", "LLM-only TP"),
                ("diting_only_tp", "DITING-only TP"),
            ],
        )
    )
    lines.extend(
        [
            "",
            "## Prompt Refinement",
            "",
        ]
    )
    lines.extend(
        markdown_table(
            prompt_rows,
            [
                ("version", "Version"),
                ("main_change", "Main change"),
                ("f1", "F1"),
                ("dus_f1", "DUS F1"),
                ("dus_tp", "DUS TP"),
                ("candidate_coverage", "Candidate coverage"),
            ],
        )
    )
    (OUT_DIR / "paper_tables.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check",
        action="store_true",
        help="Regenerate tables and print a short success message.",
    )
    parser.parse_args()

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    model_rows, category_rows, coverage_rows = generate_actual_tables()
    prompt_rows = generate_prompt_table()

    write_csv(
        OUT_DIR / "main_metrics_and_union.csv",
        model_rows,
        [
            "model",
            "f1",
            "precision",
            "catprec",
            "tp",
            "fp",
            "union_f1",
            "union_recall",
            "llm_only_tp",
            "diting_only_tp",
        ],
    )
    category_fields = ["model"]
    for short in ("udo", "ivw", "dus"):
        category_fields.extend(
            [
                f"{short}_f1",
                f"{short}_precision",
                f"{short}_recall",
                f"{short}_tp",
                f"{short}_fp",
                f"{short}_fn",
            ]
        )
    write_csv(OUT_DIR / "category_metrics.csv", category_rows, category_fields)
    write_csv(
        OUT_DIR / "chain_coverage.csv",
        coverage_rows,
        [
            "model",
            "phase3_profile",
            "sinks",
            "chains",
            "gt_lines",
            "covered",
            "uncovered",
            "coverage_percent",
            "uncovered_lines",
            "uncovered_functions",
        ],
    )
    write_csv(
        OUT_DIR / "prompt_refinement.csv",
        prompt_rows,
        ["version", "main_change", "f1", "dus_f1", "dus_tp", "candidate_coverage"],
    )
    write_markdown(model_rows, prompt_rows)

    print(f"Wrote regenerated tables to {OUT_DIR}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
