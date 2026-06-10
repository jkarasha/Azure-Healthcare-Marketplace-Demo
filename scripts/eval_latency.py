#!/usr/bin/env python3
"""Run MCP latency/reliability evals from JSON-RPC test cases.

Config format:
{
  "defaults": {
    "iterations": 5,
    "concurrency": 3,
    "timeout_seconds": 20,
    "min_success_rate": 1.0,
    "max_p95_ms": 2000
  },
  "cases": [
    {
      "name": "npi-tools-list",
      "url": "http://localhost:7071/mcp",
      "headers": {},
      "request": {"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}
    }
  ]
}
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return float("nan")
    ordered = sorted(values)
    rank = max(0, min(len(ordered) - 1, math.ceil((pct / 100.0) * len(ordered)) - 1))
    return ordered[rank]


def _expand_env(data: object) -> object:
    if isinstance(data, dict):
        return {k: _expand_env(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_expand_env(v) for v in data]
    if isinstance(data, str):
        return os.path.expandvars(data)
    return data


def _run_once(case: dict, timeout_seconds: float) -> dict:
    started = time.perf_counter()
    payload = json.dumps(case["request"]).encode("utf-8")
    headers = {"Content-Type": "application/json", **case.get("headers", {})}

    request = urllib.request.Request(
        url=case["url"],
        data=payload,
        headers=headers,
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except urllib.error.HTTPError as exc:
        status = exc.code
        body = exc.read().decode("utf-8", errors="replace")
    except Exception as exc:
        elapsed_ms = (time.perf_counter() - started) * 1000.0
        return {
            "ok": False,
            "latency_ms": elapsed_ms,
            "status": None,
            "error": str(exc),
        }

    elapsed_ms = (time.perf_counter() - started) * 1000.0

    try:
        data = json.loads(body)
    except Exception:
        return {
            "ok": False,
            "latency_ms": elapsed_ms,
            "status": status,
            "error": "non-json response",
        }

    ok = status == 200 and "result" in data and "error" not in data
    return {
        "ok": ok,
        "latency_ms": elapsed_ms,
        "status": status,
        "error": None if ok else data.get("error") or "missing result",
    }


def _evaluate_case(case: dict, iterations: int, concurrency: int, timeout_seconds: float) -> dict:
    results: list[dict] = []

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [executor.submit(_run_once, case, timeout_seconds) for _ in range(iterations)]
        for fut in as_completed(futures):
            results.append(fut.result())

    latencies = [r["latency_ms"] for r in results]
    success = [r for r in results if r["ok"]]
    failures = [r for r in results if not r["ok"]]

    return {
        "name": case["name"],
        "iterations": iterations,
        "success_count": len(success),
        "failure_count": len(failures),
        "success_rate": len(success) / iterations if iterations else 0.0,
        "p50_ms": _percentile(latencies, 50),
        "p95_ms": _percentile(latencies, 95),
        "max_ms": max(latencies) if latencies else float("nan"),
        "failures": failures[:3],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP latency/reliability eval runner")
    parser.add_argument("--config", required=True, help="Path to eval config JSON")
    parser.add_argument("--iterations", type=int, default=None, help="Override iterations")
    parser.add_argument("--concurrency", type=int, default=None, help="Override concurrency")
    parser.add_argument(
        "--code",
        default=None,
        help="Azure Functions key appended as ?code= to each case URL (e.g. docker-default-key)",
    )
    return parser.parse_args()


def _apply_code(url: str, code: str) -> str:
    """Append the Functions access key to a URL as a query parameter."""
    if not code:
        return url
    separator = "&" if "?" in url else "?"
    return f"{url}{separator}code={code}"


def main() -> int:
    args = parse_args()
    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        return 1

    raw_config = json.loads(config_path.read_text(encoding="utf-8"))
    config = _expand_env(raw_config)

    defaults = config.get("defaults", {})
    iterations = args.iterations or int(defaults.get("iterations", 5))
    concurrency = args.concurrency or int(defaults.get("concurrency", 3))
    timeout_seconds = float(defaults.get("timeout_seconds", 20))
    min_success_rate = float(defaults.get("min_success_rate", 1.0))
    max_p95_ms = float(defaults.get("max_p95_ms", 2000))

    cases = config.get("cases", [])
    if not cases:
        print("No eval cases found in config")
        return 1

    code = args.code if args.code is not None else os.environ.get("MCP_FUNCTION_CODE", "")
    if code:
        for case in cases:
            if "url" in case:
                case["url"] = _apply_code(case["url"], code)

    print(f"Running MCP evals: {len(cases)} case(s), iterations={iterations}, concurrency={concurrency}")

    overall_ok = True
    for case in cases:
        summary = _evaluate_case(case, iterations, concurrency, timeout_seconds)

        case_ok = summary["success_rate"] >= min_success_rate and summary["p95_ms"] <= max_p95_ms
        overall_ok = overall_ok and case_ok

        status = "PASS" if case_ok else "FAIL"
        print(
            f"[{status}] {summary['name']}: "
            f"success={summary['success_count']}/{summary['iterations']} "
            f"({summary['success_rate']:.0%}) "
            f"p50={summary['p50_ms']:.1f}ms p95={summary['p95_ms']:.1f}ms max={summary['max_ms']:.1f}ms"
        )

        if summary["failures"]:
            for failure in summary["failures"]:
                print(f"  - failure: status={failure.get('status')} error={failure.get('error')}")

    if not overall_ok:
        print(
            f"\nLatency eval failed. Thresholds: min_success_rate={min_success_rate:.0%}, "
            f"max_p95_ms={max_p95_ms:.0f}"
        )
        return 1

    print("\nLatency eval passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
