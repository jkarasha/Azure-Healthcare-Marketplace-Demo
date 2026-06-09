#!/usr/bin/env python3
"""Native-style eval runner using Agent Framework lab evaluation contracts.

This runner uses the public evaluation data contracts from
`agent_framework_lab_gaia`:
- Task
- Prediction
- Evaluation
- TaskResult

It is intentionally domain-local (MCP JSON-RPC checks) and does not depend on
external benchmark datasets.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from urllib.parse import urlparse, urlunparse

try:
    from agent_framework_lab_gaia import Evaluation, Prediction, Task, TaskResult
except Exception as exc:  # pragma: no cover
    raise RuntimeError("agent_framework_lab_gaia is required. Run with src/agents/.venv/bin/python") from exc


def _expand_env(value: object) -> object:
    if isinstance(value, dict):
        return {k: _expand_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_expand_env(v) for v in value]
    if isinstance(value, str):
        return os.path.expandvars(value)
    return value


def _run_task(task: Task, timeout_seconds: float) -> TaskResult:
    metadata = task.metadata or {}
    request_payload = metadata.get("request") or {}
    headers = {"Content-Type": "application/json", **(metadata.get("headers") or {})}
    url = str(metadata.get("url") or "")

    started = time.perf_counter()
    prediction = Prediction(prediction="", metadata={})

    try:
        req = urllib.request.Request(
            url=url,
            data=json.dumps(request_payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
                body = resp.read().decode("utf-8")
                status = resp.status
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            status = exc.code

        elapsed = time.perf_counter() - started

        prediction = Prediction(
            prediction=body,
            metadata={"status": status, "runtime_seconds": elapsed},
        )

        evaluation = _evaluate(task, prediction)

        return TaskResult(
            task_id=task.task_id,
            task=task,
            prediction=prediction,
            evaluation=evaluation,
            runtime_seconds=elapsed,
            error=None,
        )
    except Exception as exc:
        elapsed = time.perf_counter() - started
        return TaskResult(
            task_id=task.task_id,
            task=task,
            prediction=prediction,
            evaluation=Evaluation(is_correct=False, score=0.0, details={"error": str(exc)}),
            runtime_seconds=elapsed,
            error=str(exc),
        )


def _health_url_from_mcp_url(mcp_url: str) -> str:
    parsed = urlparse(mcp_url)
    return urlunparse(parsed._replace(path="/health", params="", query="", fragment=""))


def _is_endpoint_healthy(health_url: str, timeout_seconds: float) -> bool:
    try:
        req = urllib.request.Request(url=health_url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout_seconds) as resp:
            return 200 <= int(resp.status) < 300
    except Exception:
        return False


def _check_endpoints_ready(
    tasks: list[Task],
    wait_seconds: float,
    probe_timeout_seconds: float,
    probe_interval_seconds: float,
) -> list[tuple[str, str]]:
    endpoints: dict[str, str] = {}
    for task in tasks:
        url = str((task.metadata or {}).get("url") or "")
        if url and url not in endpoints:
            endpoints[url] = _health_url_from_mcp_url(url)

    if not endpoints:
        return []

    deadline = time.perf_counter() + max(0.0, wait_seconds)
    while True:
        missing: list[tuple[str, str]] = []
        for mcp_url, health_url in endpoints.items():
            if not _is_endpoint_healthy(health_url, timeout_seconds=probe_timeout_seconds):
                missing.append((mcp_url, health_url))

        if not missing:
            return []
        if time.perf_counter() >= deadline:
            return missing

        time.sleep(max(0.1, probe_interval_seconds))


def _evaluate(task: Task, prediction: Prediction) -> Evaluation:
    metadata = task.metadata or {}
    status = int((prediction.metadata or {}).get("status") or 0)

    required_result_keys = metadata.get("required_result_keys") or []
    min_tool_count = metadata.get("min_tool_count")

    try:
        payload = json.loads(prediction.prediction)
    except Exception:
        return Evaluation(
            is_correct=False,
            score=0.0,
            details={"reason": "non_json_response", "status": status},
        )

    if status != 200:
        return Evaluation(
            is_correct=False,
            score=0.0,
            details={"reason": "non_200", "status": status},
        )

    if "result" not in payload:
        return Evaluation(
            is_correct=False,
            score=0.0,
            details={"reason": "missing_result", "status": status},
        )

    result = payload.get("result") or {}
    missing = [k for k in required_result_keys if k not in result]
    if missing:
        return Evaluation(
            is_correct=False,
            score=0.0,
            details={"reason": "missing_keys", "missing": missing},
        )

    if min_tool_count is not None:
        tools = result.get("tools")
        if not isinstance(tools, list) or len(tools) < int(min_tool_count):
            return Evaluation(
                is_correct=False,
                score=0.0,
                details={"reason": "tool_count_below_min", "count": len(tools) if isinstance(tools, list) else None},
            )

    return Evaluation(is_correct=True, score=1.0, details={"status": status})


def _run(tasks: list[Task], parallel: int, timeout_seconds: float) -> list[TaskResult]:
    results: list[TaskResult] = []
    with ThreadPoolExecutor(max_workers=max(1, parallel)) as pool:
        futures = [pool.submit(_run_task, task, timeout_seconds) for task in tasks]
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


def _print_summary(results: list[TaskResult]) -> int:
    total = len(results)
    correct = sum(1 for r in results if r.evaluation.is_correct)
    avg_runtime = sum((r.runtime_seconds or 0.0) for r in results) / total if total else 0.0

    print(
        f"Native eval summary: {correct}/{total} passed, accuracy={correct/total if total else 0:.0%}, avg_runtime={avg_runtime:.3f}s"
    )

    for result in sorted(results, key=lambda r: r.task_id):
        status = "PASS" if result.evaluation.is_correct else "FAIL"
        print(
            f"[{status}] {result.task_id}: "
            f"score={result.evaluation.score:.1f} "
            f"runtime={result.runtime_seconds or 0.0:.3f}s"
        )
        if not result.evaluation.is_correct:
            print(f"  details={result.evaluation.details}")
            if result.error:
                print(f"  error={result.error}")

    return 0 if correct == total else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Native Agent Framework-style eval runner")
    parser.add_argument("--config", required=True, help="Path to eval config JSON")
    parser.add_argument("--parallel", type=int, default=3, help="Parallel task workers")
    parser.add_argument("--timeout-seconds", type=float, default=20.0, help="Per-request timeout")
    parser.add_argument(
        "--wait-for-servers-seconds",
        type=float,
        default=0.0,
        help="Optional time budget to wait for endpoint /health checks before running evals",
    )
    parser.add_argument(
        "--probe-timeout-seconds",
        type=float,
        default=1.5,
        help="Timeout for each endpoint /health probe",
    )
    parser.add_argument(
        "--probe-interval-seconds",
        type=float,
        default=0.5,
        help="Polling interval between endpoint readiness probes",
    )
    parser.add_argument(
        "--skip-preflight",
        action="store_true",
        help="Skip endpoint readiness preflight",
    )
    parser.add_argument("--out", default="", help="Optional JSONL output path for TaskResult records")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return 1

    config = _expand_env(json.loads(config_path.read_text(encoding="utf-8")))
    cases = config.get("cases") or []
    if not cases:
        print("No cases found in config")
        return 1

    tasks: list[Task] = []
    for case in cases:
        task_id = str(case.get("name") or f"case-{len(tasks)+1}")
        tasks.append(
            Task(
                task_id=task_id,
                question=str(case.get("description") or task_id),
                answer="pass",
                metadata={
                    "url": case.get("url"),
                    "headers": case.get("headers") or {},
                    "request": case.get("request") or {},
                    "required_result_keys": case.get("required_result_keys") or [],
                    "min_tool_count": case.get("min_tool_count"),
                },
            )
        )

    if not args.skip_preflight:
        missing = _check_endpoints_ready(
            tasks=tasks,
            wait_seconds=args.wait_for_servers_seconds,
            probe_timeout_seconds=args.probe_timeout_seconds,
            probe_interval_seconds=args.probe_interval_seconds,
        )
        if missing:
            wait_note = f" within {args.wait_for_servers_seconds:.1f}s" if args.wait_for_servers_seconds > 0 else ""
            print(f"MCP endpoint preflight failed{wait_note}:")
            for mcp_url, health_url in missing:
                print(f"  - {mcp_url} (health: {health_url})")
            print("Start missing local servers (for example, `make local-start`) and rerun.")
            return 1

    results = _run(tasks, parallel=args.parallel, timeout_seconds=args.timeout_seconds)

    if args.out:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as handle:
            for result in results:
                handle.write(json.dumps(asdict(result), default=str) + "\n")
        print(f"Wrote results: {out_path}")

    return _print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
