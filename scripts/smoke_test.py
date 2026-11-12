#!/usr/bin/env python3
"""End-to-end smoke test kundër një API të deploy-uar (APP-08).

    python scripts/smoke_test.py --api-url https://xxx.execute-api.eu-central-1.amazonaws.com [--chat]
    python scripts/smoke_test.py --api-url http://localhost:8080

Pa dependencies (vetëm stdlib), që të ekzekutohet në çdo runner.
Kthen exit code 1 nëse ndonjë kontroll dështon.
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def call(url, method="GET", body=None, timeout=35, retries=3):
    data = json.dumps(body).encode() if body is not None else None
    last = None
    for attempt in range(1, retries + 1):
        req = urllib.request.Request(url, data=data, method=method,
                                     headers={"Content-Type": "application/json"})
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                payload = json.loads(resp.read().decode())
                return resp.status, payload, time.monotonic() - start
        except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
            last = e
            # Cold start / API e sapokrijuar: prit pak dhe provo prapë
            time.sleep(5 * attempt)
    raise RuntimeError(f"{method} {url} failed after {retries} attempts: {last}")


def check(name, ok, detail):
    ok = bool(ok)
    print(f"{'PASS' if ok else 'FAIL'}  {name:<14} {detail}")
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--api-url", required=True)
    ap.add_argument("--chat", action="store_true", help="testo edhe /chat (thërret Bedrock)")
    args = ap.parse_args()
    api = args.api_url.rstrip("/")
    results = []

    status, d, t = call(f"{api}/consumption")
    recs = d.get("records", [])
    results.append(check("/consumption", status == 200 and len(recs) > 0
                         and {"timestamp", "global_active_power_kwh"} <= recs[0].keys(),
                         f"{status} records={len(recs)} {t:.1f}s"))

    status, d, t = call(f"{api}/forecast?horizon_hours=24")
    preds = d.get("predictions", [])
    results.append(check("/forecast", status == 200 and len(preds) > 0
                         and {"timestamp", "predicted_kwh"} <= preds[0].keys(),
                         f"{status} predictions={len(preds)} {t:.1f}s"))

    status, d, t = call(f"{api}/anomalies")
    anoms = d.get("anomalies", [])
    results.append(check("/anomalies", status == 200 and isinstance(anoms, list)
                         and all({"timestamp", "severity"} <= a.keys() for a in anoms),
                         f"{status} anomalies={len(anoms)} {t:.1f}s"))

    if args.chat:
        status, d, t = call(f"{api}/chat", "POST",
                            {"message": "What was my peak consumption hour?", "session_id": "smoke-test"},
                            timeout=35, retries=2)
        results.append(check("/chat", status == 200 and isinstance(d.get("answer"), str) and d["answer"],
                             f"{status} answer={d.get('answer', '')[:60]!r} {t:.1f}s"))

    print(f"\n{sum(results)}/{len(results)} checks passed")
    return 0 if all(results) else 1


if __name__ == "__main__":
    sys.exit(main())
