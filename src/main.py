#!/usr/bin/env python3
"""main.py – TA 静的解析ドライバ (プロンプトモード対応版)"""
from __future__ import annotations
import sys, argparse, os, json, subprocess, re
from pathlib import Path
import time
from datetime import datetime, timedelta

from build import ensure_ta_db
from classify.classifier import classify_functions          # type: ignore
from metrics.run_history import RunHistoryManager

# ------------------------------------------------------------

def run(cmd: list[str], cwd: Path, verbose: bool, phase_name: str = ""):
    """
    コマンドを実行し、エラー時は適切に処理
    
    Args:
        cmd: 実行するコマンド
        cwd: 作業ディレクトリ
        verbose: 詳細出力フラグ
        phase_name: フェーズ名（エラーメッセージ用）
    """
    if verbose:
        print(f"[INFO] $ {' '.join(cmd)}  (cwd={cwd})")
    
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
        
        # エラーが発生した場合
        if res.returncode != 0:
            error_msg = f"Command failed with return code {res.returncode}"
            if phase_name:
                error_msg = f"[ERROR] {phase_name} failed: {error_msg}"
            else:
                error_msg = f"[ERROR] {error_msg}"
            
            print(error_msg)
            
            # エラー出力を表示
            if res.stderr:
                print(f"[STDERR] {res.stderr[:500]}")  # 最初の500文字のみ表示
            # 非verboseでも、標準出力の末尾を表示して原因特定しやすくする
            if res.stdout:
                stdout_lines = res.stdout.strip().splitlines()
                tail = "\n".join(stdout_lines[-20:])
                if tail:
                    print(f"[STDOUT tail]\n{tail}")
            
            # verboseモードの場合は完全な出力を表示
            if verbose:
                print(f"[WARN]   ↳ rc={res.returncode}")
                if res.stdout:
                    print(f"[STDOUT] {res.stdout}")
                if res.stderr and len(res.stderr) > 500:
                    print(f"[STDERR Full] {res.stderr}")
            
            # エラー時は常に終了（verboseに関わらず）
            sys.exit(res.returncode)
        
        # 成功時でもverboseモードなら出力を表示
        if verbose and res.stdout:
            print(f"[STDOUT] {res.stdout}")
            
    except subprocess.TimeoutExpired:
        error_msg = f"Command timed out after 600 seconds"
        if phase_name:
            error_msg = f"[ERROR] {phase_name}: {error_msg}"
        else:
            error_msg = f"[ERROR] {error_msg}"
        print(error_msg)
        sys.exit(124)  # timeout用の終了コード
        
    except Exception as e:
        error_msg = f"Unexpected error: {e}"
        if phase_name:
            error_msg = f"[ERROR] {phase_name}: {error_msg}"
        else:
            error_msg = f"[ERROR] {error_msg}"
        print(error_msg)
        sys.exit(1)

# ------------------------------------------------------------

def format_duration(seconds: float) -> str:
    """秒数を人間が読みやすい形式にフォーマット"""
    td = timedelta(seconds=seconds)
    hours = int(td.total_seconds() // 3600)
    minutes = int((td.total_seconds() % 3600) // 60)
    secs = td.total_seconds() % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs:.2f}s"
    elif minutes > 0:
        return f"{minutes}m {secs:.2f}s"
    else:
        return f"{secs:.2f}s"

# ------------------------------------------------------------

def clean_project_dependencies(proj_path: Path, verbose: bool = False):
    """
    プロジェクトの古い依存関係ファイルをクリーンアップ
    
    Args:
        proj_path: プロジェクトのルートパス
        verbose: 詳細出力を有効にするか
    """
    if verbose:
        print(f"[INFO] Cleaning dependencies for {proj_path.name}")
    
    cleaned_count = 0
    
    # .d ファイル（依存関係ファイル）を削除
    for dep_file in proj_path.rglob("*.d"):
        # キャッシュディレクトリやバイナリファイルをスキップ
        if any(skip in str(dep_file) for skip in ['/cache/', '/.git/', '/node_modules/', '/db-cpp/']):
            continue
            
        try:
            # 古いツールチェーンパスを含むファイルかチェック
            # バイナリファイルの可能性があるので、バイナリモードで読み込み
            with open(dep_file, 'rb') as f:
                content_bytes = f.read()
            
            # UTF-8でデコードを試みる
            try:
                content = content_bytes.decode('utf-8', errors='strict')
            except UnicodeDecodeError:
                # バイナリファイルの場合はスキップ
                continue
            
            if "/mnt/disk/toolschain" in content:
                dep_file.unlink()
                cleaned_count += 1
                if verbose:
                    print(f"  - Removed stale dependency: {dep_file.relative_to(proj_path)}")
        except Exception as e:
            if verbose and "codec can't decode" not in str(e):
                print(f"[WARN] Failed to process {dep_file}: {e}")
    
    # .o ファイル（オブジェクトファイル）も念のため削除
    for obj_file in proj_path.rglob("*.o"):
        try:
            obj_file.unlink()
            cleaned_count += 1
        except Exception as e:
            if verbose:
                print(f"[WARN] Failed to remove {obj_file}: {e}")
    
    # make clean を実行（エラーは無視）
    for makefile_dir in [proj_path, proj_path / "ta", proj_path / "host"]:
        if (makefile_dir / "Makefile").exists():
            try:
                result = subprocess.run(
                    ["make", "clean"],
                    cwd=makefile_dir,
                    capture_output=True,
                    text=True
                )
                if verbose and result.returncode == 0:
                    print(f"  - Executed 'make clean' in {makefile_dir.relative_to(proj_path)}")
            except subprocess.TimeoutExpired:
                if verbose:
                    print(f"[WARN] 'make clean' timeout in {makefile_dir}")
            except Exception:
                pass  # エラーは無視
    
    if verbose and cleaned_count > 0:
        print(f"  ✓ Cleaned {cleaned_count} files")

# ------------------------------------------------------------

def auto_devkit() -> Path | None:
    if (env := os.getenv("TA_DEV_KIT_DIR")):
        return Path(env)
    for p in Path.cwd().rglob("export-ta_*/include"):
        return p.parent
    return None

DEVKIT = auto_devkit()
if DEVKIT:
    os.environ["TA_DEV_KIT_DIR"] = str(DEVKIT)

# ------------------------------------------------------------

FIXED_ANALYSIS_MODE = "Hybrid (DITING rules only) (excluding debug macros)"
FIXED_TOKEN_TRACKING = True
FIXED_DEBUG_MACROS = False


def resolve_bad_partitioning_path(project: Path) -> Path:
    """
    bad-partitioning パスを解決する。
    既定の benchmark/bad-partitioning が無い場合は
    benchmark/partitioningE/bad-partitioning をフォールバックする。
    """
    if project.exists():
        return project

    if project.name == "bad-partitioning":
        alt = Path("benchmark/partitioningE/bad-partitioning")
        if alt.exists():
            print(f"[INFO] Using fallback path: {alt}")
            return alt

    return project


def resolve_project_and_ta(project: Path) -> tuple[Path, Path]:
    """
    プロジェクトルートと ta ディレクトリを解決する。
    - <project>/ta がある場合: それを採用
    - 引数が ta ディレクトリ自体の場合: 親をプロジェクトルートとして採用
    """
    project = resolve_bad_partitioning_path(project).resolve()
    ta_candidate = project / "ta"
    if ta_candidate.is_dir():
        return project, ta_candidate
    if project.name == "ta" and project.is_dir():
        return project.parent, project
    return project, ta_candidate


def get_active_llm_identity() -> tuple[str, str]:
    """現在アクティブなLLM provider/modelを設定ファイルから取得する。"""
    try:
        from llm_settings.config_manager import LLMConfig
        cfg = LLMConfig()
        provider = cfg.get_active_provider()
        model = str(cfg.get_provider_config(provider).get("model", "unknown"))
        return provider, model
    except Exception:
        return "unknown", "unknown"


def sanitize_dir_name(value: str) -> str:
    """ディレクトリ名として安全な文字列に変換する。"""
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._-")
    return cleaned or "unknown"


def resolve_output_root(ta_dir: Path, llm_model: str, output_root: Path | None) -> Path:
    """
    解析結果のルートディレクトリを決定する。
    - output_root 未指定: <ta>/<model名>
    - output_root 指定時:
      - 絶対パス: そのまま使用
      - 相対パス: <ta>/<output_root>
    """
    if output_root is None:
        return ta_dir / sanitize_dir_name(llm_model)
    if output_root.is_absolute():
        return output_root
    return ta_dir / output_root


def allocate_run_results_dir(results_root: Path) -> tuple[Path, int]:
    """
    results_root 以下に results_N を採番して新規作成する。
    並列実行時に同じ番号を掴んだ場合は再試行する。
    Returns:
        (新規 results ディレクトリ, N)
    """
    results_root.mkdir(parents=True, exist_ok=True)

    while True:
        max_index = 0
        for child in results_root.iterdir():
            if not child.is_dir():
                continue
            m = re.fullmatch(r"results_(\d+)", child.name)
            if m:
                max_index = max(max_index, int(m.group(1)))

        run_index = max_index + 1
        res_dir = results_root / f"results_{run_index}"
        try:
            res_dir.mkdir(parents=True, exist_ok=False)
            return res_dir, run_index
        except FileExistsError:
            # 別プロセスが同じ番号を先に作成した場合は採番をやり直す。
            continue


def process_project(
    proj: Path,
    identify_py: Path,
    v: bool,
    prompt_version: str = "v2",
    output_root: Path | None = None,
):
    # 実行時間計測開始
    start_time = time.time()
    start_datetime = datetime.now()
    
    proj, ta_dir = resolve_project_and_ta(proj)
    if not ta_dir.is_dir():
        print(f"[WARN] {proj.name}: 'ta/' missing → skip")
        return

    llm_provider, llm_model = get_active_llm_identity()
    results_root = resolve_output_root(ta_dir, llm_model, output_root)
    res_dir, run_index = allocate_run_results_dir(results_root)

    print(f"\n=== Project: {proj.name} / TA: {ta_dir.name} ===")
    print(f"[INFO] Active LLM: {llm_provider} / {llm_model}")
    print(f"[INFO] Results root: {results_root}")
    print(f"[INFO] Run output dir: {res_dir} (run #{run_index})")
    
    print(f"[INFO] Analysis mode: {FIXED_ANALYSIS_MODE}")
    print("[INFO] Token tracking: enabled")
    print("[INFO] Debug macros: excluded")

    vulnerabilities = res_dir / f"{ta_dir.name}_vulnerabilities.json"
    analysis_completed = False
    
    # 各フェーズの実行時間を記録する辞書
    phase_times = {}
    
    # エラーハンドリングを強化
    try:
        # 解析前クリーンアップは常に実行
        phase_start = time.time()
        clean_project_dependencies(proj, verbose=v)
        phase_times["cleaning"] = time.time() - phase_start

        # Step1: データベース構築
        phase_start = time.time()
        try:
            ta_db = ensure_ta_db(ta_dir, proj, DEVKIT, v)
        except Exception as e:
            print(f"[ERROR] Failed to build database: {e}")
            sys.exit(1)
        phase_times["build_db"] = time.time() - phase_start

        # Step2: 関数分類
        phase_start = time.time()
        try:
            users, externals = classify_functions(ta_dir, ta_db)
            phase12 = res_dir / f"{ta_dir.name}_phase12.json"
            phase12.write_text(json.dumps({
                "project_root": str(ta_dir),
                "user_defined_functions": users,
                "external_declarations": externals,
            }, indent=2, ensure_ascii=False))
            print(f"[phase1-2] → {phase12}")
        except Exception as e:
            print(f"[ERROR] Failed in phase 1-2 (function classification): {e}")
            sys.exit(1)
        phase_times["phase1-2"] = time.time() - phase_start

        # Step3 (シンク特定フェーズ) - LLM-onlyモードは常に適用
        phase_start = time.time()
        sinks = res_dir / f"{ta_dir.name}_sinks.json"
        identify_cmd = [
            sys.executable, str(identify_py),
            "-i", str(phase12),
            "-o", str(sinks),
            "--llm-only",
            "--prompt-version", prompt_version
        ]
        run(identify_cmd, ta_dir, v, "Phase 3: Identify Sinks")
        print(f"[phase3 ] → {sinks}\n")
        phase_times["phase3_identify_sinks"] = time.time() - phase_start

        # Phase4: 統合版候補フロー生成（旧Phase3.1〜3.4を統合）
        phase_start = time.time()
        flows_py = Path(__file__).parent / "identify_flows" / "generate_candidate_flows.py"
        
        candidate_flows = res_dir / f"{ta_dir.name}_candidate_flows.json"
        
        # 統合版のコマンドライン引数
        flow_cmd = [
            sys.executable, str(flows_py),
            "--compile-db", str(ta_db),
            "--sinks", str(sinks),
            "--phase12", str(phase12),
            "--sources", "TA_InvokeCommandEntryPoint,TA_OpenSessionEntryPoint",
            "--output", str(candidate_flows)
        ]
        
        # オプション引数
        if os.environ.get("TA_DEV_KIT_DIR"):
            flow_cmd.extend(["--devkit", os.environ.get("TA_DEV_KIT_DIR")])
        if v:
            flow_cmd.append("--verbose")

        print(f"[phase4 ] Integrated candidate flow generation")
        print(f"          → {flows_py.name} --compile-db {ta_db.name} --sinks {sinks.name} --phase12 {phase12.name} --sources ... --output {candidate_flows.name}")
        
        run(flow_cmd, ta_dir, v, "Phase 4: Generate Candidate Flows (Integrated)")
        print(f"[phase4 ] → {candidate_flows}\n")
        phase_times["phase4_generate_candidate_flows"] = time.time() - phase_start

        # Phase5: テイント解析と脆弱性検査
        phase_start = time.time()
        taint_py = Path(__file__).parent / "analyze_vulnerabilities" / "taint_analyzer.py"

        taint_cmd = [sys.executable, str(taint_py),
                    "--flows", str(candidate_flows),
                    "--phase12", str(phase12),
                    "--output", str(vulnerabilities),
                    "--prompt-version", prompt_version]

        # 詳細ログ
        if v:
            taint_cmd.append("--verbose")

        print(f"[phase5_command] → python3 {taint_py.name} {' '.join(taint_cmd[2:])}")
        run(taint_cmd, ta_dir, v, "Phase 5: Taint Analysis")
        phase_times["phase5_taint_analysis"] = time.time() - phase_start

        # Phase6: HTMLレポート生成
        phase_start = time.time()
        report_py = Path(__file__).parent / "report" / "generate_report.py"
        
        report_html = res_dir / f"{ta_dir.name}_vulnerability_report.html"
        
        report_cmd = [sys.executable, str(report_py),
             "--sinks", str(sinks),
             "--flows", str(candidate_flows),
             "--vulnerabilities", str(vulnerabilities),
             "--phase12", str(phase12),
             "--project-name", proj.name,
             "--output", str(report_html)]
        
        if v:
            print(f"[DEBUG] Report command: {' '.join(report_cmd)}")
        print(f"[phase6_command] → python3 {report_py} {' '.join(report_cmd[1:])}")
        run(report_cmd, ta_dir, v, "Phase 6: Generate Report")
        print(f"[phase6 ] → {report_html}\n")
        phase_times["phase6_generate_report"] = time.time() - phase_start

        analysis_completed = True
        print(f"[SUCCESS] All phases completed successfully for {proj.name}")

    except Exception as e:
        # 予期しないエラーをキャッチ
        print(f"[ERROR] Unexpected error in process_project: {e}")
        import traceback
        if v:
            traceback.print_exc()
        sys.exit(1)
        
    finally:
        # 実行時間計測終了
        end_time = time.time()
        end_datetime = datetime.now()
        total_time = end_time - start_time
        time_file = res_dir / "time.txt"
        
        # 実行時間をファイルに記録
        try:
            with open(time_file, 'w', encoding='utf-8') as f:
                f.write(f"Project: {proj.name}\n")
                f.write(f"TA: {ta_dir.name}\n")
                f.write(f"LLM Provider: {llm_provider}\n")
                f.write(f"LLM Model: {llm_model}\n")
                f.write(f"Results Root: {results_root}\n")
                f.write(f"Run Index: {run_index}\n")
                f.write(f"Analysis Mode: {FIXED_ANALYSIS_MODE}\n")
                f.write(f"Token Tracking: {'Enabled' if FIXED_TOKEN_TRACKING else 'Disabled'}\n")
                f.write(f"Debug Macros: {'Included' if FIXED_DEBUG_MACROS else 'Excluded'}\n")
                f.write(f"=" * 60 + "\n")
                f.write(f"Start Time: {start_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"End Time: {end_datetime.strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write(f"Total Duration: {format_duration(total_time)}\n")
                f.write(f"Total Seconds: {total_time:.2f}s\n")
                f.write(f"=" * 60 + "\n")
                f.write(f"Phase Breakdown:\n")
                
                # 各フェーズの実行時間を記録
                for phase_name, phase_time in phase_times.items():
                    percentage = (phase_time / total_time) * 100 if total_time > 0 else 0
                    f.write(f"  {phase_name:40s}: {format_duration(phase_time):15s} ({percentage:5.1f}%)\n")
            
            print(f"[INFO] Execution time recorded in: {time_file}")
            print(f"[INFO] Total execution time: {format_duration(total_time)}")
        except Exception as e:
            print(f"[WARN] Failed to write time.txt: {e}")

        # 実行履歴を更新（成功時のみ）
        if analysis_completed and vulnerabilities.exists():
            try:
                history = RunHistoryManager(results_root)
                record = history.append_from_result_files(
                    vulnerabilities_json=vulnerabilities,
                    project_name=proj.name,
                    time_txt=time_file
                )
                if record:
                    print(
                        "[INFO] Run history updated: "
                        f"total_issues={record.total_issues} "
                        f"(vuln={record.vulnerability_lines}, structural_risk={record.structural_risk_lines})"
                    )
                    print(f"[INFO]   ↳ {results_root / 'run_history.csv'}")
                    print(f"[INFO]   ↳ {results_root / 'model_averages.csv'}")
                    consensus_json = history.generate_consensus_vulnerabilities(
                        required_runs=5,
                        min_votes=3,
                        output_filename="ta_vulnerabilies.json"
                    )
                    if consensus_json:
                        print(
                            "[INFO]   ↳ "
                            f"{consensus_json} (consensus: vulnerable lines appearing in >=3 of latest 5 runs)"
                        )
                    else:
                        print(
                            "[INFO] Consensus JSON not generated yet "
                            f"({history.get_run_count()}/5 runs)"
                        )

                    compare_script = Path(__file__).parent / "metrics" / "compare_prompt_versions.py"
                    if compare_script.exists():
                        print("[INFO] Compare with prompt_v1 baseline:")
                        print(
                            f"[INFO]   ↳ python {compare_script} "
                            f"--current {res_dir} "
                            f"--baseline /workspace/prompt_v1_output/gpt5-mini-bad-partitioning/gpt-5-mini-ta_vulnerabilities.json "
                            f"--ground-truth /workspace/bad-partitioning-ta_groundtruth_labels/category_labels/ground_truth_labels.csv"
                        )
                    taint_compare_script = Path(__file__).parent / "metrics" / "compare_taint_sanitizers.py"
                    if taint_compare_script.exists():
                        print("[INFO] Compare taint propagation / sanitizer recognition:")
                        print(
                            f"[INFO]   ↳ python {taint_compare_script} "
                            f"--current {res_dir} "
                            f"--baseline /workspace/prompt_v1_output/gpt5-mini-bad-partitioning/gpt-5-mini-conversations.jsonl "
                            f"--labels-dir /workspace/bad-partitioning-ta_groundtruth_labels/flow_labels/taint_sanitizer_labels"
                        )
            except Exception as e:
                print(f"[WARN] Failed to update run history: {e}")

# ---------------------------------------------------------------------------

if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="bad-partitioning 専用 TA Static Analysis Driver"
    )
    
    ap.add_argument(
        "-p",
        "--project",
        type=Path,
        default=Path("benchmark/bad-partitioning"),
        help="bad-partitioning プロジェクトパス (default: benchmark/bad-partitioning)"
    )
    ap.add_argument("--verbose", action="store_true",
                    help="Enable verbose output")
    ap.add_argument(
        "--prompt-version",
        default="v2",
        help="使用するプロンプトバージョン (例: v1, v2, v3, または絶対パス)"
    )
    ap.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "解析結果ルートディレクトリ。未指定時は ta/<model名>。"
            "相対パスは ta/ 配下、絶対パスはそのまま使用。"
        )
    )
    args = ap.parse_args()

    print("="*60)
    print("TA Static Analysis Driver")
    print("="*60)
    print(f"Target Project: {args.project}")
    print(f"Analysis Configuration: {FIXED_ANALYSIS_MODE}")
    print(f"Token Tracking: {'Enabled' if FIXED_TOKEN_TRACKING else 'Disabled'}")
    print(f"Debug Macros: {'Included' if FIXED_DEBUG_MACROS else 'Excluded'}")
    print(f"Prompt Version: {args.prompt_version}")
    if args.output_root is not None:
        print(f"Output Root: {args.output_root}")
    print("="*60)

    identify_py = Path(__file__).resolve().parent / "identify_sinks" / "identify_sinks.py"
    try:
        process_project(
            args.project,
            identify_py,
            args.verbose,
            args.prompt_version,
            args.output_root,
        )
    except SystemExit as e:
        print(f"[ERROR] Analysis failed for project {args.project} with exit code {e.code}")
        sys.exit(e.code)
    except Exception as e:
        print(f"[ERROR] Unexpected error processing project {args.project}: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)
