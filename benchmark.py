#!/usr/bin/env python3
"""
benchmark.py — Run the crawler against multiple model configs and compare.

Usage:
    python benchmark.py                                       # all configs, 10 pages
    python benchmark.py --configs qwen3-vl-8b qwen3-vl-4b
    python benchmark.py --pages 20
    python benchmark.py --configs qwen3-vl-8b --pages 5
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from tabulate import tabulate

PROJECT_DIR = Path(__file__).parent
CONFIGS_DIR = PROJECT_DIR / "configs"
RESULTS_DIR = PROJECT_DIR / "results"
HEALTH_URL  = "http://127.0.0.1:8000/health"
PYTHON      = str(PROJECT_DIR / ".venv" / "bin" / "python")


# ── helpers ───────────────────────────────────────────────────────────────────

def _server_alive() -> bool:
    try:
        return httpx.get(HEALTH_URL, timeout=2).status_code == 200
    except Exception:
        return False


def _wait_server_up(timeout: int = 360) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _server_alive():
            return True
        time.sleep(3)
    return False


def _wait_server_down(timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not _server_alive():
            return
        time.sleep(2)


def _read_config(name: str) -> dict:
    path = CONFIGS_DIR / f"{name}.env"
    out: dict = {}
    if path.exists():
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            k, _, v = line.partition("=")
            out[k.strip()] = v.strip()
    return out


def _latest_stats(before_json: set) -> Path | None:
    """Return the *_stats.json written by the most recent main.py run."""
    candidates = [
        p for p in RESULTS_DIR.glob("*_stats.json")
        if time.time() - p.stat().st_mtime < 300
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def _latest_json(before: set) -> Path | None:
    new = set(RESULTS_DIR.glob("*_results.json")) - before
    return max(new, key=lambda p: p.stat().st_mtime) if new else None


# ── per-config run ─────────────────────────────────────────────────────────────

def run_config(config_name: str, pages: int) -> dict:
    cfg      = _read_config(config_name)
    model_id = cfg.get("MODEL_ID", "?")

    print(f"\n{'═' * 62}")
    print(f"  Config : {config_name}")
    print(f"  Model  : {model_id}")
    print(f"  Pages  : {pages}")
    print(f"{'═' * 62}")

    env      = {**os.environ, "MODEL_CONFIG": config_name, "MAX_PAGES": str(pages)}
    existing = set(RESULTS_DIR.glob("*_results.json"))
    server   = None
    wall_s   = 0.0

    try:
        # — start server —
        print("  Starting server ...", end="", flush=True)
        server = subprocess.Popen(
            ["bash", str(PROJECT_DIR / "server.sh")],
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            preexec_fn=os.setsid,
        )
        t_boot = time.monotonic()
        if not _wait_server_up(timeout=360):
            print(" TIMEOUT")
            return {"config": config_name, "model_id": model_id, "status": "server_timeout"}
        boot_s = round(time.monotonic() - t_boot, 1)
        print(f" ready in {boot_s}s")

        # — run crawler —
        print("  Crawling ...", end="", flush=True)
        t0 = time.monotonic()
        subprocess.run(
            [PYTHON, str(PROJECT_DIR / "main.py")],
            env=env,
            check=False,
        )
        wall_s = round(time.monotonic() - t0, 1)
        print(f" done in {wall_s}s")

    finally:
        if server is not None:
            try:
                os.killpg(os.getpgid(server.pid), signal.SIGTERM)
                server.wait(timeout=15)
            except Exception:
                pass
        _wait_server_down(timeout=30)

    # — read stats sidecar written by main.py —
    sidecar = _latest_stats(existing)
    if sidecar:
        s = json.loads(sidecar.read_text())
        return {
            "config":       config_name,
            "model_id":     model_id,
            "status":       "ok",
            "total":        s["urls_processed"],
            "successful":   s["successful"],
            "errors":       s["errors"],
            "success_pct":  s["success_pct"],
            "total_s":      s["total_s"],
            "throughput_s": s["throughput_s"],
            "avg_url_s":    s["avg_url_s"],
            "min_url_s":    s["min_url_s"],
            "p50_url_s":    s["p50_url_s"],
            "p95_url_s":    s["p95_url_s"],
            "max_url_s":    s["max_url_s"],
            "wall_s":       wall_s,
            "boot_s":       boot_s,
            "results_file": s["results_file"],
        }

    # — fallback: recompute from results JSON —
    result_file = _latest_json(existing)
    if not result_file:
        return {"config": config_name, "model_id": model_id, "status": "no_results",
                "wall_s": wall_s, "boot_s": boot_s}

    data   = json.loads(result_file.read_text())
    ok     = [r for r in data if "error" not in r]
    errors = [r for r in data if "error"     in r]
    durs   = sorted(r["_duration_s"] for r in data)
    avg    = round(sum(durs) / len(durs), 1) if durs else 0
    def _pct(lst, p):
        if not lst: return 0
        k = (len(lst) - 1) * p / 100
        lo, hi = int(k), min(int(k) + 1, len(lst) - 1)
        return round(lst[lo] + (lst[hi] - lst[lo]) * (k - lo), 2)
    return {
        "config":       config_name,
        "model_id":     model_id,
        "status":       "ok",
        "total":        len(data),
        "successful":   len(ok),
        "errors":       len(errors),
        "success_pct":  round(len(ok) / len(data) * 100) if data else 0,
        "total_s":      round(wall_s, 1),
        "throughput_s": round(wall_s / len(data), 2) if data else 0,
        "avg_url_s":    avg,
        "min_url_s":    durs[0]  if durs else 0,
        "p50_url_s":    _pct(durs, 50),
        "p95_url_s":    _pct(durs, 95),
        "max_url_s":    durs[-1] if durs else 0,
        "wall_s":       wall_s,
        "boot_s":       boot_s,
        "results_file": result_file.name,
    }


# ── summary table ──────────────────────────────────────────────────────────────

def _table_row(r: dict) -> list:
    if r.get("status") != "ok":
        return [r["config"], r.get("model_id", "?"), "—/—", "—",
                "—", "—", "—", "—", r.get("wall_s", "—"), "—", r.get("boot_s", "—"), r["status"]]
    return [
        r["config"],
        r["model_id"],
        f"{r['successful']}/{r['total']}",
        f"{r['success_pct']}%",
        r["avg_url_s"],
        r["min_url_s"],
        r["p50_url_s"],
        r["p95_url_s"],
        r["max_url_s"],
        r["total_s"],
        r["throughput_s"],
        r["boot_s"],
        "✓",
    ]


def print_summary(results: list, pages: int) -> None:
    headers = ["Config", "Model", "OK/Total", "Success%",
               "Avg(s)", "Min(s)", "P50(s)", "P95(s)", "Max(s)",
               "Total(s)", "s/url", "Boot(s)", "Status"]
    rows = [_table_row(r) for r in results]
    print(f"\n  Benchmark — {datetime.now():%Y-%m-%d %H:%M}  |  {pages} pages/model\n")
    print(tabulate(rows, headers=headers, tablefmt="rounded_outline"))


# ── entry point ────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--configs", nargs="+", metavar="NAME",
                    help="Config names to run (default: all configs/*.env)")
    ap.add_argument("--pages", type=int, default=10,
                    help="URLs per model run (default: 10)")
    ap.add_argument("--output", default=None,
                    help="JSON output path (default: benchmark_TIMESTAMP.json)")
    args = ap.parse_args()

    names = args.configs or sorted(p.stem for p in CONFIGS_DIR.glob("*.env"))
    if not names:
        sys.exit("No configs found in configs/. Run from the project directory.")

    print(f"\nBenchmarking {len(names)} config(s) × {args.pages} pages each:")
    for n in names:
        print(f"  • {n}")

    results = []
    for name in names:
        results.append(run_config(name, args.pages))
        time.sleep(3)  # brief gap between runs

    print_summary(results, args.pages)

    ts  = datetime.now().strftime("%Y-%m-%d-%H:%M")
    out = Path(args.output) if args.output else RESULTS_DIR / f"benchmark_{ts}.json"
    out.write_text(json.dumps(
        {"timestamp": ts, "pages_per_model": args.pages, "results": results},
        indent=2,
    ))
    print(f"\n  Saved → {out}\n")


if __name__ == "__main__":
    main()
