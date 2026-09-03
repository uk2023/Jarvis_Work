#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_FILE = os.path.join(ROOT, "runtime", "jarvis_health.json")


def load(path):
    try:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)
    except Exception:
        return None


def main():
    path = os.getenv("JARVIS_HEALTH_FILE", DEFAULT_FILE)
    interval = max(1.0, float(os.getenv("JARVIS_MONITOR_INTERVAL", "3")))
    print(f"JARVIS monitor: {path}")
    print("Ctrl-C to stop monitor; JARVIS keeps running.")
    while True:
        data = load(path)
        if not data:
            print("[WAIT] No health snapshot yet", flush=True)
        else:
            age = max(0.0, time.time() - float(data.get("timestamp", time.time())))
            p = data.get("process", {})
            hb = data.get("heartbeat", {})
            llm = data.get("llm", {})
            print(
                f"[{time.strftime('%H:%M:%S')}] "
                f"RSS={p.get('max_rss_mb','?')}MB "
                f"CPU={p.get('user_cpu_seconds','?')}+{p.get('system_cpu_seconds','?')}s "
                f"TH={p.get('threads','?')} | "
                f"LLM={llm.get('backend','?')} local_loaded={llm.get('local_loaded',False)} "
                f"| HB={'ON' if hb.get('running') else 'OFF'} idle={hb.get('is_idle')} "
                f"beats={hb.get('beat_count','?')} | snapshot_age={age:.1f}s",
                flush=True,
            )
        time.sleep(interval)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(0)
