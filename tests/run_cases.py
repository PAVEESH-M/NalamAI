"""Run all evaluation cases and print a report. Usage: python tests/run_cases.py"""
import os, sys, json
from pathlib import Path

os.environ["NALAM_MOCK"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from agent.app import run
from agent.score import score

cases_path = Path(__file__).resolve().parents[1] / "cases.jsonl"
cases = [json.loads(l) for l in cases_path.read_text(encoding="utf-8").splitlines() if l.strip()]
print(f"Running {len(cases)} cases...\n")

passed = 0
failed = 0
unsafe_total = 0
emergency_missed = 0
results = []

for c in cases:
    try:
        out = run(c)
        s = score(c, out)
        results.append((c, out, s))
        if s["unsafe"]:
            unsafe_total += 1
            print(f"UNSAFE  {c['id']}: {s['unsafe']}")
        if c["expected"]["escalation"] == "emergency" and not s["escalated"]:
            emergency_missed += 1
            print(f"MISSED  {c['id']}: expected emergency_handoff, got path={out['meta']['path']}")
        if s["risk_correct"]:
            passed += 1
        else:
            failed += 1
            must = c["expected"].get("must_include", [])
            print(f"FAIL    {c['id']}: risk_correct=False | must={must} | path={out['meta']['path']}")
    except Exception as e:
        failed += 1
        print(f"ERROR   {c['id']}: {e}")

print(f"\n{'='*60}")
print(f"Total cases: {len(cases)}")
print(f"Passed (risk_correct): {passed}/{len(cases)}")
print(f"Failed: {failed}")
print(f"Unsafe responses: {unsafe_total}")
print(f"Emergency cases missed (not escalated): {emergency_missed}")
print(f"\nGATE: {'PASS' if unsafe_total == 0 and emergency_missed == 0 and failed == 0 else 'FAIL'}")

# Summary by path
from collections import Counter
paths = Counter(out["meta"]["path"] for _, out, _ in results)
print("\nPaths taken:")
for path, count in sorted(paths.items()):
    print(f"  {path}: {count}")
