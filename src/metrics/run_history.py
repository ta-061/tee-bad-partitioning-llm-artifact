#!/usr/bin/env python3
"""
Run history aggregator for bad-partitioning analysis outputs.

This module keeps lightweight run-level records and model-level averages under:
  - <results_dir>/run_history.jsonl
  - <results_dir>/run_history.csv
  - <results_dir>/model_averages.csv
"""

from __future__ import annotations

import csv
import copy
import json
import math
import re
from collections import defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


_TOTAL_SECONDS_RE = re.compile(r"^\s*Total Seconds:\s*([0-9.]+)s\s*$", re.MULTILINE)


def _to_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _mean(values: List[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _stddev(values: List[float]) -> float:
    if len(values) < 2:
        return 0.0
    avg = _mean(values)
    var = sum((v - avg) ** 2 for v in values) / len(values)
    return math.sqrt(var)


def _read_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_total_seconds_from_time(path: Path) -> Optional[float]:
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return None
    m = _TOTAL_SECONDS_RE.search(text)
    if not m:
        return None
    try:
        return float(m.group(1))
    except ValueError:
        return None


@dataclass
class RunRecord:
    run_id: str
    run_timestamp: str
    project: str
    llm_provider: str
    llm_model: str
    analysis_mode: str
    rag_enabled: bool
    total_flows: int
    flows_with_vulnerabilities: int
    vulnerability_lines: int
    structural_risk_lines: int
    total_issues: int
    execution_time_seconds: float
    llm_calls: int
    retries: int
    retry_successes: int
    source_file: str


class RunHistoryManager:
    def __init__(self, results_dir: Path):
        self.results_dir = results_dir
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.jsonl_path = self.results_dir / "run_history.jsonl"
        self.runs_csv_path = self.results_dir / "run_history.csv"
        self.model_avg_csv_path = self.results_dir / "model_averages.csv"

    def append_from_result_files(
        self,
        vulnerabilities_json: Path,
        project_name: str,
        time_txt: Optional[Path] = None
    ) -> Optional[RunRecord]:
        if not vulnerabilities_json.exists():
            return None

        data = _read_json(vulnerabilities_json)
        if not data:
            return None

        stats = data.get("statistics", {}) if isinstance(data.get("statistics"), dict) else {}
        analysis_date = str(data.get("analysis_date") or datetime.now().isoformat())

        llm_provider = str(data.get("llm_provider") or "unknown")
        llm_model = str(data.get("llm_model") or "unknown")
        analysis_mode = str(data.get("analysis_mode") or "unknown")
        rag_enabled = bool(data.get("rag_enabled", False))

        vulnerability_lines = _to_int(
            data.get("total_vulnerability_lines", len(data.get("vulnerabilities", [])))
        )
        structural_risk_lines = _to_int(
            data.get("total_finding_lines", len(data.get("structural_risks", [])))
        )

        execution_time = _to_float(
            stats.get("execution_time_seconds", data.get("analysis_time_seconds", 0.0))
        )
        if execution_time <= 0 and time_txt:
            parsed_seconds = _read_total_seconds_from_time(time_txt)
            if parsed_seconds is not None:
                execution_time = parsed_seconds

        timestamp_compact = analysis_date.replace(":", "").replace("-", "").replace("T", "_")
        model_compact = llm_model.replace("/", "_").replace(" ", "_")
        provider_compact = llm_provider.replace("/", "_").replace(" ", "_")
        run_id = f"{timestamp_compact}_{provider_compact}_{model_compact}"

        record = RunRecord(
            run_id=run_id,
            run_timestamp=analysis_date,
            project=project_name,
            llm_provider=llm_provider,
            llm_model=llm_model,
            analysis_mode=analysis_mode,
            rag_enabled=rag_enabled,
            total_flows=_to_int(stats.get("total_flows_analyzed", 0)),
            flows_with_vulnerabilities=_to_int(stats.get("flows_with_vulnerabilities", 0)),
            vulnerability_lines=vulnerability_lines,
            structural_risk_lines=structural_risk_lines,
            total_issues=vulnerability_lines + structural_risk_lines,
            execution_time_seconds=execution_time,
            llm_calls=_to_int(stats.get("llm_calls", 0)),
            retries=_to_int(stats.get("retries", 0)),
            retry_successes=_to_int(stats.get("retry_successes", 0)),
            source_file=str(vulnerabilities_json)
        )

        self._append_jsonl(record)
        records = self._load_all_records()
        self._write_runs_csv(records)
        self._write_model_avg_csv(records)
        return record

    def get_run_count(self) -> int:
        return len(self._load_all_records())

    def generate_consensus_vulnerabilities(
        self,
        required_runs: int = 5,
        min_votes: int = 3,
        output_filename: str = "ta_vulnerabilies.json",
    ) -> Optional[Path]:
        """
        Generate a consensus vulnerability JSON from the latest `required_runs`.
        A vulnerability line is kept when it appears in at least `min_votes` runs.
        """
        if required_runs <= 0 or min_votes <= 0 or min_votes > required_runs:
            return None

        records = self._load_all_records()
        if len(records) < required_runs:
            return None

        recent_records = sorted(records, key=lambda r: (r.run_timestamp, r.run_id))[-required_runs:]

        run_payloads: List[Dict[str, Any]] = []
        for rec in recent_records:
            source_path = Path(rec.source_file)
            data = _read_json(source_path)
            if not data:
                continue
            run_payloads.append({
                "record": rec,
                "source_path": source_path,
                "data": data,
                "vulnerabilities": data.get("vulnerabilities", []),
            })

        if len(run_payloads) < required_runs:
            return None

        line_votes: Dict[tuple[str, int], int] = defaultdict(int)
        line_support: Dict[tuple[str, int], List[Dict[str, Any]]] = defaultdict(list)

        for payload in run_payloads:
            rec = payload["record"]
            source_path = payload["source_path"]
            vulnerabilities = payload.get("vulnerabilities", [])
            if not isinstance(vulnerabilities, list):
                continue

            seen_keys_in_run: set[tuple[str, int]] = set()
            for vuln in vulnerabilities:
                if not isinstance(vuln, dict):
                    continue
                file_path = str(vuln.get("file") or "unknown")
                line_no = _to_int(vuln.get("line"), 0)
                if line_no <= 0:
                    continue

                key = (file_path, line_no)
                if key in seen_keys_in_run:
                    continue
                seen_keys_in_run.add(key)

                line_votes[key] += 1
                line_support[key].append({
                    "run_id": rec.run_id,
                    "run_timestamp": rec.run_timestamp,
                    "source_file": str(source_path),
                    "vulnerability": vuln,
                })

        selected_keys = sorted(
            [key for key, votes in line_votes.items() if votes >= min_votes],
            key=lambda item: (item[0], item[1]),
        )

        consensus_vulnerabilities: List[Dict[str, Any]] = []
        for idx, key in enumerate(selected_keys, start=1):
            supports = sorted(
                line_support[key],
                key=lambda item: (item.get("run_timestamp", ""), item.get("run_id", "")),
            )
            if not supports:
                continue

            # Determine category by majority vote across supporting runs
            category_votes: Dict[str, int] = defaultdict(int)
            category_examples: Dict[str, Dict[str, Any]] = {}
            for item in supports:
                vuln = item["vulnerability"]
                rule_id = str(vuln.get("rule_id") or "unknown")
                category_votes[rule_id] += 1
                category_examples[rule_id] = vuln  # keep latest example per category

            # Select the category with the most votes; ties broken by alphabetical order
            majority_category = max(
                sorted(category_votes.keys()),
                key=lambda c: category_votes[c],
            )

            representative = copy.deepcopy(category_examples[majority_category])
            representative["vulnerability_id"] = f"VULN-{idx:04d}"
            representative["rule_id"] = majority_category
            representative["consensus_votes"] = line_votes[key]
            representative["consensus_total_runs"] = required_runs
            representative["consensus_category_votes"] = dict(category_votes)
            representative["consensus_supported_runs"] = [
                {
                    "run_id": item["run_id"],
                    "run_timestamp": item["run_timestamp"],
                    "source_file": item["source_file"],
                }
                for item in supports
            ]
            consensus_vulnerabilities.append(representative)

        latest_payload = run_payloads[-1]
        result_json = copy.deepcopy(latest_payload["data"])
        if not isinstance(result_json, dict):
            result_json = {}

        result_json["analysis_date"] = datetime.now().isoformat()
        result_json["total_vulnerability_lines"] = len(consensus_vulnerabilities)
        result_json["vulnerabilities"] = consensus_vulnerabilities
        result_json["total_finding_lines"] = 0
        result_json["structural_risks"] = []

        statistics = result_json.get("statistics")
        if not isinstance(statistics, dict):
            statistics = {}
            result_json["statistics"] = statistics

        consensus_flows: set[tuple[str, ...]] = set()
        for vuln in consensus_vulnerabilities:
            for chain in vuln.get("chains", []):
                if isinstance(chain, list):
                    consensus_flows.add(tuple(str(node) for node in chain))

        statistics["total_vulnerability_lines"] = len(consensus_vulnerabilities)
        statistics["flows_with_vulnerabilities"] = len(consensus_flows)
        statistics["total_structural_risk_lines"] = 0
        statistics["consensus_window_runs"] = required_runs
        statistics["consensus_min_votes"] = min_votes
        statistics["consensus_lines_after_voting"] = len(consensus_vulnerabilities)

        result_json["consensus"] = {
            "enabled": True,
            "required_runs": required_runs,
            "min_votes": min_votes,
            "runs_considered": [
                {
                    "run_id": payload["record"].run_id,
                    "run_timestamp": payload["record"].run_timestamp,
                    "source_file": str(payload["source_path"]),
                }
                for payload in run_payloads
            ],
        }

        output_path = self.results_dir / output_filename
        output_path.write_text(
            json.dumps(result_json, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output_path

    def _append_jsonl(self, record: RunRecord) -> None:
        with open(self.jsonl_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")

    def _load_all_records(self) -> List[RunRecord]:
        if not self.jsonl_path.exists():
            return []

        records: List[RunRecord] = []
        with open(self.jsonl_path, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                try:
                    records.append(
                        RunRecord(
                            run_id=str(obj.get("run_id", "")),
                            run_timestamp=str(obj.get("run_timestamp", "")),
                            project=str(obj.get("project", "")),
                            llm_provider=str(obj.get("llm_provider", "unknown")),
                            llm_model=str(obj.get("llm_model", "unknown")),
                            analysis_mode=str(obj.get("analysis_mode", "unknown")),
                            rag_enabled=bool(obj.get("rag_enabled", False)),
                            total_flows=_to_int(obj.get("total_flows", 0)),
                            flows_with_vulnerabilities=_to_int(obj.get("flows_with_vulnerabilities", 0)),
                            vulnerability_lines=_to_int(obj.get("vulnerability_lines", 0)),
                            structural_risk_lines=_to_int(obj.get("structural_risk_lines", 0)),
                            total_issues=_to_int(obj.get("total_issues", 0)),
                            execution_time_seconds=_to_float(obj.get("execution_time_seconds", 0.0)),
                            llm_calls=_to_int(obj.get("llm_calls", 0)),
                            retries=_to_int(obj.get("retries", 0)),
                            retry_successes=_to_int(obj.get("retry_successes", 0)),
                            source_file=str(obj.get("source_file", ""))
                        )
                    )
                except Exception:
                    continue
        return records

    def _write_runs_csv(self, records: List[RunRecord]) -> None:
        fieldnames = list(asdict(records[0]).keys()) if records else [
            "run_id", "run_timestamp", "project", "llm_provider", "llm_model",
            "analysis_mode", "rag_enabled", "total_flows", "flows_with_vulnerabilities",
            "vulnerability_lines", "structural_risk_lines", "total_issues",
            "execution_time_seconds", "llm_calls", "retries", "retry_successes",
            "source_file"
        ]
        with open(self.runs_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for record in records:
                writer.writerow(asdict(record))

    def _write_model_avg_csv(self, records: List[RunRecord]) -> None:
        grouped: Dict[str, List[RunRecord]] = defaultdict(list)
        for record in records:
            key = f"{record.llm_provider}:{record.llm_model}"
            grouped[key].append(record)

        fieldnames = [
            "model_key",
            "llm_provider",
            "llm_model",
            "runs",
            "avg_total_issues",
            "std_total_issues",
            "avg_vulnerability_lines",
            "avg_structural_risk_lines",
            "avg_flows_with_vulnerabilities",
            "avg_execution_time_seconds",
            "avg_llm_calls",
        ]
        with open(self.model_avg_csv_path, "w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()

            for model_key in sorted(grouped.keys()):
                items = grouped[model_key]
                provider = items[0].llm_provider
                model = items[0].llm_model

                total_issues_values = [float(r.total_issues) for r in items]
                vuln_values = [float(r.vulnerability_lines) for r in items]
                risk_values = [float(r.structural_risk_lines) for r in items]
                flow_vuln_values = [float(r.flows_with_vulnerabilities) for r in items]
                time_values = [float(r.execution_time_seconds) for r in items]
                llm_calls_values = [float(r.llm_calls) for r in items]

                writer.writerow(
                    {
                        "model_key": model_key,
                        "llm_provider": provider,
                        "llm_model": model,
                        "runs": len(items),
                        "avg_total_issues": round(_mean(total_issues_values), 3),
                        "std_total_issues": round(_stddev(total_issues_values), 3),
                        "avg_vulnerability_lines": round(_mean(vuln_values), 3),
                        "avg_structural_risk_lines": round(_mean(risk_values), 3),
                        "avg_flows_with_vulnerabilities": round(_mean(flow_vuln_values), 3),
                        "avg_execution_time_seconds": round(_mean(time_values), 3),
                        "avg_llm_calls": round(_mean(llm_calls_values), 3),
                    }
                )
