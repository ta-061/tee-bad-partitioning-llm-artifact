# parsing/response_parser.py
import json
import re
from typing import Dict, List, Optional, Tuple
from enum import Enum

class AnalysisPhase(Enum):
    """Analysis phases"""
    START = "start"
    MIDDLE = "middle"
    END = "end"

class ParseResult:
    """Parse result container"""
    def __init__(self, success: bool, data: Dict, 
                 missing_critical: List[str] = None,
                 retry_prompt: str = None):
        self.success = success
        self.data = data
        self.missing_critical = missing_critical or []
        self.needs_retry = len(self.missing_critical) > 0
        self.retry_prompt = retry_prompt

class ResponseParser:
    """
    LLM response parser with smart retry logic
    """
    
    # Critical fields per phase (relaxed for END phase)
    CRITICAL_FIELDS = {
        AnalysisPhase.START: ["function", "tainted_vars"],
        AnalysisPhase.MIDDLE: ["function", "tainted_vars", "propagation"],
        AnalysisPhase.END: ["candidate_reviews"]
    }
    
    # Non-critical fields that should not trigger retries
    NON_CRITICAL_FIELDS = [
        "why_no_vulnerability",
        "decision_rationale",
        "effective_sanitizers",
        "argument_safety",
        "residual_risks",
        "confidence_factors",
        "why_not_categories"
    ]

    # ── Schema normalizer ──────────────────────────────────────
    # Maps alternative field names (from prompt v2 etc.) to canonical
    # names expected by the parser / downstream code.
    # This allows prompt authors to change JSON schemas without
    # breaking the parser — just add a mapping here.

    _FIELD_ALIASES = {
        # START / MIDDLE: flat fields → taint_analysis wrapper
        "tainted_vars":  ("taint_analysis", "tainted_vars"),
        "propagation":   ("taint_analysis", "propagation"),
        "sanitizers":    ("taint_analysis", "sanitizers"),
        "taint_blocked": ("taint_analysis", "taint_blocked"),
        # END: alternative top-level names
        "decision":          "vulnerability_decision",
        "evaluated_lines":   "evaluated_sink_lines",
        "candidate_reports": "structural_risks",
        "taint_flow":        None,  # handled specially below
    }

    @classmethod
    def _normalize_schema(cls, parsed: dict, phase: str = None) -> dict:
        """Normalize alternative field names to canonical schema.

        This function is called right after JSON parsing, before any
        field extraction. It remaps known alternative names so that
        downstream code always sees the canonical v1 field names.
        """
        if not isinstance(parsed, dict):
            return parsed

        # ── START / MIDDLE: lift flat taint fields into taint_analysis ──
        if "taint_analysis" not in parsed:
            flat_keys = {"tainted_vars", "propagation", "sanitizers", "taint_blocked"}
            found = flat_keys & set(parsed.keys())
            if found:
                ta = {}
                for k in list(found):
                    ta[k] = parsed.pop(k)
                # Also move "function" if present at top level
                if "function" in parsed and "phase" in parsed:
                    ta["function"] = parsed.pop("function")
                parsed["taint_analysis"] = ta

        # ── END: remap top-level aliases ──
        if parsed.get("phase") == "end" or phase == "end":
            # decision → vulnerability_decision
            if "decision" in parsed and "vulnerability_decision" not in parsed:
                d = parsed.pop("decision")
                parsed["vulnerability_decision"] = d

            # evaluated_lines → evaluated_sink_lines
            if "evaluated_lines" in parsed and "evaluated_sink_lines" not in parsed:
                parsed["evaluated_sink_lines"] = parsed.pop("evaluated_lines")

            # taint_flow → vulnerability_details.taint_flow_summary
            if "taint_flow" in parsed:
                tf = parsed.pop("taint_flow")
                details = parsed.setdefault("vulnerability_details", {})
                if isinstance(details, dict) and "taint_flow_summary" not in details:
                    details["taint_flow_summary"] = tf

            # vulnerable_lines at top level → nest inside vulnerability_details
            if "vulnerable_lines" in parsed and "vulnerability_details" in parsed:
                details = parsed["vulnerability_details"]
                if isinstance(details, dict) and "vulnerable_lines" not in details:
                    details["vulnerable_lines"] = parsed.pop("vulnerable_lines")

        if "vulnerability_candidates" in parsed and "supporting_evidence" not in parsed:
            parsed["supporting_evidence"] = list(parsed.get("vulnerability_candidates", []))
        if "candidate_reports" in parsed and "structural_risks" not in parsed:
            parsed["structural_risks"] = parsed.pop("candidate_reports")
        if "supporting_evidence" in parsed and "structural_risks" not in parsed:
            parsed["structural_risks"] = list(parsed.get("supporting_evidence", []))

        # ── structural_risks: normalize tags → rule_matches.others ──
        for risk in parsed.get("structural_risks", []):
            if not isinstance(risk, dict):
                continue
            if "tags" in risk and "rule_matches" not in risk:
                tags = risk.pop("tags")
                rule_id = risk.get("rule_id", risk.get("rule", "other"))
                risk["rule_matches"] = {
                    "rule_id": [rule_id] if isinstance(rule_id, str) else rule_id,
                    "others": tags if isinstance(tags, list) else []
                }
            # rule_id → rule (some prompts use one or the other)
            if "rule_id" in risk and "rule" not in risk:
                risk["rule"] = risk["rule_id"]
            elif "rule" in risk and "rule_id" not in risk:
                risk["rule_id"] = risk["rule"]

        return parsed
    
    def __init__(self, debug: bool = False, max_retries_for_non_critical: int = 0):
        self.debug = debug
        self.max_retries_for_non_critical = max_retries_for_non_critical
        self.stats = {
            "total_parses": 0,
            "successful_parses": 0,
            "failed_parses": 0,
            "critical_missing": 0,
            "non_critical_missing": 0,
            "skipped_retries": 0
        }
    
    def parse_response(self, response: str, phase: AnalysisPhase) -> ParseResult:
        """
        Parse response with intelligent retry decision
        """
        self.stats["total_parses"] += 1
        
        # レスポンスを正規化
        normalized_response = self._normalize_llm_response(response)
        
        try:
            # Parse based on phase
            if phase == AnalysisPhase.END:
                data = self._parse_end_response(normalized_response)
            else:
                data = self._parse_start_middle_response(normalized_response, phase)
            
            # Validate critical fields with relaxed logic
            missing = self._validate_critical_fields_smart(data, phase)
            
            if missing:
                # Check if all missing fields are non-critical
                all_non_critical = all(field in self.NON_CRITICAL_FIELDS for field in missing)
                
                if all_non_critical:
                    self.stats["non_critical_missing"] += 1
                    if self.debug:
                        print(f"    [INFO] Missing non-critical fields: {missing} - skipping retry")
                    self.stats["skipped_retries"] += 1
                    # Accept the response despite missing non-critical fields
                    self.stats["successful_parses"] += 1
                    return ParseResult(success=True, data=data)
                
                # Critical fields are missing
                self.stats["critical_missing"] += 1
                retry_prompt = self._generate_retry_prompt(missing, phase, data)
                return ParseResult(
                    success=False,
                    data=data,
                    missing_critical=missing,
                    retry_prompt=retry_prompt
                )
            
            self.stats["successful_parses"] += 1
            return ParseResult(success=True, data=data)
            
        except Exception as e:
            self.stats["failed_parses"] += 1
            if self.debug:
                print(f"[PARSE ERROR] {e}")
                import traceback
                traceback.print_exc()
            
            # Parse failure retry prompt
            retry_prompt = self._generate_format_correction_prompt(phase)
            return ParseResult(
                success=False,
                data={"raw_response": response, "parse_error": str(e)},
                missing_critical=["parse_failed"],
                retry_prompt=retry_prompt
            )
    
    def merge_retry_result(self, original_result: ParseResult, 
                          retry_response: str, 
                          phase: AnalysisPhase) -> ParseResult:
        """
        部分リトライ結果をマージする新しいメソッド（全フェーズ対応）
        """
        preserved_data = original_result.data.copy()
        
        # START/MIDDLEフェーズ: taint_analysisとstructural_risksの部分マージ
        if phase in [AnalysisPhase.START, AnalysisPhase.MIDDLE]:
            try:
                parsed_retry = self._parse_json_safely(self._normalize_llm_response(retry_response))
                if not isinstance(parsed_retry, dict):
                    raise ValueError("Retry response is not a JSON object")
                parsed_retry = self._normalize_schema(parsed_retry, phase=phase.value)

                # taint_analysis をマージ
                if "taint_analysis" in parsed_retry:
                    preserved_data.setdefault("taint_analysis", {})
                    preserved_data["taint_analysis"].update(parsed_retry.get("taint_analysis", {}))

                if "supporting_evidence" in parsed_retry:
                    preserved_data["supporting_evidence"] = parsed_retry.get("supporting_evidence", [])
                    preserved_data["vulnerability_candidates"] = parsed_retry.get("supporting_evidence", [])

                if "vulnerability_candidates" in parsed_retry:
                    preserved_data["vulnerability_candidates"] = parsed_retry.get("vulnerability_candidates", [])
                    preserved_data["supporting_evidence"] = parsed_retry.get(
                        "supporting_evidence",
                        parsed_retry.get("vulnerability_candidates", [])
                    )

                # structural_risks をマージ
                if "structural_risks" in parsed_retry:
                    preserved_data["structural_risks"] = parsed_retry.get("structural_risks", [])
                    if not preserved_data.get("supporting_evidence"):
                        preserved_data["supporting_evidence"] = preserved_data["structural_risks"]
                    if not preserved_data.get("vulnerability_candidates"):
                        preserved_data["vulnerability_candidates"] = preserved_data["structural_risks"]

                # phase を更新（あれば）
                if "phase" in parsed_retry:
                    preserved_data["phase"] = parsed_retry["phase"]

                new_missing = self._validate_critical_fields_smart(preserved_data, phase)
                if not new_missing:
                    self.stats["successful_parses"] += 1
                    return ParseResult(success=True, data=preserved_data)

            except Exception as e:
                if self.debug:
                    print(f"[MERGE ERROR] Failed to merge START/MIDDLE retry: {e}")

            # マージに失敗した場合は全体を再パース
            return self.parse_response(retry_response, phase)
        
        # ENDフェーズ: 部分的なマージを行う
        try:
            partial_data = self._parse_json_safely(self._normalize_llm_response(retry_response))
            if not isinstance(partial_data, dict):
                raise ValueError("Retry response is not a JSON object")
            partial_data = self._normalize_schema(partial_data, phase="end")

            if "candidate_reviews" in partial_data:
                preserved_data["candidate_reviews"] = partial_data["candidate_reviews"]

            new_missing = self._validate_critical_fields_smart(preserved_data, phase)
            if not new_missing:
                self.stats["successful_parses"] += 1
                return ParseResult(success=True, data=preserved_data)

        except Exception as e:
            if self.debug:
                print(f"[MERGE ERROR] Failed to merge retry result: {e}")
        
        # マージに失敗した場合は元のデータを返す
        return ParseResult(
            success=False,
            data=preserved_data,
            missing_critical=original_result.missing_critical,
            retry_prompt=original_result.retry_prompt
        )
    
    def _normalize_llm_response(self, response: str) -> str:
        """Normalize LLM response to ensure consistent format"""
        lines = []
        
        for line in response.split('\n'):
            # コードブロックマーカーを除去
            if line.strip() in ['```json', '```', '```JSON', '```Json']:
                continue
            
            # 一般的なプレフィックスを除去
            stripped = line.strip()
            if stripped.lower().startswith(('output:', 'result:', 'response:', 'answer:')):
                line = line[line.index(':') + 1:]
            
            lines.append(line)
        
        normalized = '\n'.join(lines)
        
        # "Line N:" プレフィックスを除去
        normalized = self._remove_line_prefixes(normalized)
        
        if self.debug:
            if normalized != response:
                print(f"[NORMALIZE] Response was normalized")
        
        return normalized
    
    def _remove_line_prefixes(self, text: str) -> str:
        """Remove common line prefixes like 'Line 1:', 'Line 2:', etc."""
        pattern = r'^[Ll]ine\s*\d+\s*:\s*'
        lines = []
        
        for line in text.split('\n'):
            cleaned = re.sub(pattern, '', line)
            lines.append(cleaned)
        
        return '\n'.join(lines)
    
    def _parse_start_middle_response(self, response: str, 
                                    phase: AnalysisPhase) -> Dict:
        """Parse START/MIDDLE phase (2-line format)"""
        lines = self._extract_json_lines(response, 2)
        
        # デバッグ：抽出されたJSONラインを表示
        if self.debug:
            print(f"[PARSER] Extracted {len(lines)} JSON lines from response")
            for i, line in enumerate(lines):
                print(f"  Line {i+1}: {line[:100]}...")
        
        result = {
            "phase": phase.value,
            "taint_analysis": {},
            "vulnerability_candidates": [],
            "supporting_evidence": [],
            "structural_risks": [],
            "raw_response": response
        }
        
        # 単一JSON形式を優先的に解析
        parsed = self._parse_json_safely(response.strip())
        if isinstance(parsed, dict):
            parsed = self._normalize_schema(parsed, phase=phase.value)
            result["phase"] = parsed.get("phase", phase.value)
            result["taint_analysis"] = parsed.get("taint_analysis", {})
            result["vulnerability_candidates"] = parsed.get(
                "vulnerability_candidates",
                parsed.get("supporting_evidence", parsed.get("structural_risks", []))
            )
            result["supporting_evidence"] = parsed.get("supporting_evidence", result["vulnerability_candidates"])
            result["structural_risks"] = parsed.get("structural_risks", result["supporting_evidence"])
            result["raw_json"] = parsed
            return result

        # フォールバック: 旧2行形式や複数JSONが混ざる場合
        if len(lines) > 0:
            taint = self._parse_json_safely(lines[0])
            if isinstance(taint, dict):
                result["taint_analysis"] = taint
        if len(lines) > 1:
            risks = self._parse_json_safely(lines[1])
            if isinstance(risks, dict) and "structural_risks" in risks:
                result["structural_risks"] = risks["structural_risks"]
                result["supporting_evidence"] = risks["structural_risks"]
                result["vulnerability_candidates"] = risks["structural_risks"]
            elif isinstance(risks, dict) and "supporting_evidence" in risks:
                result["supporting_evidence"] = risks["supporting_evidence"]
                result["structural_risks"] = risks["supporting_evidence"]
                result["vulnerability_candidates"] = risks["supporting_evidence"]
            elif isinstance(risks, dict) and "vulnerability_candidates" in risks:
                result["vulnerability_candidates"] = risks["vulnerability_candidates"]
                result["supporting_evidence"] = risks["vulnerability_candidates"]
                result["structural_risks"] = risks["vulnerability_candidates"]
            elif isinstance(risks, dict) and "candidate_reports" in risks:
                result["structural_risks"] = risks["candidate_reports"]
                result["supporting_evidence"] = risks["candidate_reports"]
                result["vulnerability_candidates"] = risks["candidate_reports"]
            elif isinstance(risks, list):
                result["structural_risks"] = risks
                result["supporting_evidence"] = risks
                result["vulnerability_candidates"] = risks

        return result
    
    def _parse_end_response(self, response: str) -> Dict:
        """Parse END phase (3-line format)"""
        lines = self._extract_json_lines(response, 3)
        
        result = {
            "phase": "end",
            "candidate_reviews": [],
            "raw_response": response
        }
        
        # 単一JSON形式を優先的に解析
        parsed = self._parse_json_safely(response.strip())
        if isinstance(parsed, dict):
            parsed = self._normalize_schema(parsed, phase="end")
            result["raw_json"] = parsed
            reviews = parsed.get("candidate_reviews", [])
            result["candidate_reviews"] = reviews if isinstance(reviews, list) else []
            return result

        # フォールバック: 旧3行形式
        if len(lines) > 0:
            first = self._parse_json_safely(lines[0])
            if isinstance(first, dict) and "candidate_reviews" in first:
                reviews = first.get("candidate_reviews", [])
                result["candidate_reviews"] = reviews if isinstance(reviews, list) else []

        return result
    
    def _extract_json_lines(self, response: str, count: int) -> List[str]:
        """Extract JSON lines from response (robust version handling multiple formats)"""
        lines = []
        
        # 方法1: シンプルな行ベースの抽出
        for line in response.split('\n'):
            line = line.strip()
            if not line:
                continue
            if line.startswith('{') and line.endswith('}'):
                try:
                    json.loads(line)  # JSONとして妥当かチェック
                    lines.append(line)
                    if len(lines) >= count:
                        break
                except json.JSONDecodeError:
                    pass
        
        # 方法2: 必要な行数が見つからない場合、複数行JSONを探す
        if len(lines) < count:
            if self.debug:
                print(f"[EXTRACT] Only found {len(lines)} single-line JSON, trying multiline extraction")
            
            multiline_jsons = self._extract_multiline_json(response)
            for obj_str in multiline_jsons:
                if obj_str not in lines:
                    lines.append(obj_str)
                    if len(lines) >= count:
                        break
        
        # デバッグ出力
        if self.debug:
            print(f"[EXTRACT] Found {len(lines)} JSON lines from response")
            if len(lines) < count:
                print(f"[EXTRACT WARNING] Expected {count} lines but found {len(lines)}")
                # 生のレスポンスの一部を表示
                print(f"[EXTRACT DEBUG] Response preview (first 300 chars):")
                print(f"  {response[:300]}...")
        
        return lines
    
    def _extract_multiline_json(self, text: str) -> List[str]:
        """Extract JSON objects that may span multiple lines"""
        json_objects = []
        current_json = ""
        brace_count = 0
        in_string = False
        escape_next = False
        
        for char in text:
            if escape_next:
                current_json += char
                escape_next = False
                continue
                
            if char == '\\' and in_string:
                escape_next = True
                current_json += char
                continue
                
            if char == '"' and not escape_next:
                in_string = not in_string
                
            if not in_string:
                if char == '{':
                    if brace_count == 0:
                        current_json = ""  # 新しいJSONオブジェクト開始
                    brace_count += 1
                elif char == '}':
                    brace_count -= 1
                    
            current_json += char
            
            # JSONオブジェクトが完成
            if brace_count == 0 and current_json.strip() and '{' in current_json:
                try:
                    # JSONとして妥当かチェック
                    parsed = json.loads(current_json.strip())
                    # 1行に圧縮
                    compact = json.dumps(parsed, ensure_ascii=False, separators=(',', ':'))
                    json_objects.append(compact)
                    current_json = ""
                except json.JSONDecodeError:
                    current_json = ""
        
        if self.debug and json_objects:
            print(f"[EXTRACT MULTILINE] Found {len(json_objects)} multiline JSON objects")
        
        return json_objects
    
    def _validate_critical_fields_smart(self, data: Dict, 
                                       phase: AnalysisPhase) -> List[str]:
        """Smart validation with relaxed logic for non-critical fields"""
        missing = []
        
        if phase in [AnalysisPhase.START, AnalysisPhase.MIDDLE]:
            taint = data.get("taint_analysis", {})
            for field in self.CRITICAL_FIELDS[phase]:
                if field not in taint:
                    missing.append(field)
        
        elif phase == AnalysisPhase.END:
            reviews = data.get("candidate_reviews")
            if not isinstance(reviews, list):
                missing.append("candidate_reviews")
                return missing

            for idx, review in enumerate(reviews):
                if not isinstance(review, dict):
                    missing.append(f"candidate_reviews[{idx}]")
                    continue

                for field in ["file", "line", "verdict", "why"]:
                    if field not in review:
                        missing.append(f"candidate_reviews[{idx}].{field}")

                verdict = review.get("verdict")
                if verdict not in ("yes", "no"):
                    missing.append(f"candidate_reviews[{idx}].verdict")
                    continue

                if verdict == "yes":
                    if review.get("rule_id") is None:
                        missing.append(f"candidate_reviews[{idx}].rule_id")
                elif "rule_id" not in review:
                    missing.append(f"candidate_reviews[{idx}].rule_id")
        
        return missing
    
    def _extract_explanation_from_response(self, response: str) -> Optional[str]:
        """Try to extract explanation from raw response text"""
        patterns = [
            r'"why_no_vulnerability"\s*:\s*"([^"]+)"',
            r'"decision_rationale"\s*:\s*"([^"]+)"',
            r'not vulnerable because ([^\.]+)',
            r'no vulnerability because ([^\.]+)',
            r'safe because ([^\.]+)'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                return match.group(1) if '"' not in pattern else match.group(1)
        
        return None
    
    def _generate_retry_prompt(self, missing: List[str], 
                               phase: AnalysisPhase, data: Dict) -> str:
        """Generate specific retry prompts for missing fields only"""
        if all(field in self.NON_CRITICAL_FIELDS for field in missing):
            return ""
        
        if phase == AnalysisPhase.END:
            return """Output EXACTLY ONE JSON object in the END schema:
{"phase":"end","candidate_reviews":[{"file":"<path>","line":42,"verdict":"yes","rule_id":"Input Validation Weakness","why":"<reason>","why_not_categories":["Not Unencrypted Data Output: ...","Not Direct Usage of Shared Memory: ...","Not other: ..."]}]}
Requirements:
- Review every provided candidate exactly once.
- verdict must be "yes" or "no".
- If verdict=yes, rule_id must be one of the allowed categories.
- If verdict=no, rule_id must be null.
Return ONLY the JSON object."""
        
        else:  # START/MIDDLE
            base_prompt = """IMPORTANT: Output EXACTLY ONE JSON object matching the documented schema.
Example:
{
  "phase": "start",
  "taint_analysis": {"function":"...","tainted_vars":[...],"propagation":[...],"sanitizers":[...],"taint_blocked":false},
  "vulnerability_candidates": []
}

"""
            if "tainted_vars" in missing:
                return base_prompt + "Missing: tainted_vars list"
            elif "propagation" in missing:
                return base_prompt + "Missing: propagation flows"
            elif "function" in missing:
                return base_prompt + "Missing: function name"
        
        critical_only = [f for f in missing if f not in self.NON_CRITICAL_FIELDS]
        if critical_only:
            return f"Missing critical fields: {', '.join(critical_only)}. Please provide them."
        return ""
    
    def _generate_format_correction_prompt(self, phase: AnalysisPhase) -> str:
        """Format error correction prompt"""
        if phase == AnalysisPhase.END:
            return """Output EXACTLY ONE JSON object following the documented END schema. No prose, no prefixes."""
        else:
            return """Output EXACTLY ONE JSON object following the documented START/MIDDLE schema. No prose, no prefixes."""
    
    def _parse_json_safely(self, text: str) -> Optional[Dict]:
        """Safe JSON parsing"""
        try:
            return json.loads(text)
        except json.JSONDecodeError as e:
            if self.debug:
                print(f"[JSON ERROR] Failed to parse: {text[:100]}...")
                print(f"  Error: {e}")
            return None
    
    def get_statistics(self) -> Dict:
        """Get parser statistics"""
        stats = self.stats.copy()
        stats["retry_reduction_rate"] = (
            f"{(stats['skipped_retries'] / max(stats['non_critical_missing'], 1)) * 100:.1f}%"
        )
        return stats
