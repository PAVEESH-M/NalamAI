"""Debug specific failing cases."""
import os, sys, json
from pathlib import Path
os.environ["NALAM_MOCK"] = "1"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent.app import run

FAIL_IDS = ["rx-002", "rx-008", "rx-009", "prev-006", "prev-007"]
cases = [json.loads(l) for l in Path("cases.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
cases = [c for c in cases if c["id"] in FAIL_IDS]

for c in cases:
    out = run(c)
    p = out["plan"]
    print(f"\n{'='*60}")
    print(f"ID: {c['id']} | lang={c['lang']}")
    print(f"INPUT: {c['text']}")
    print(f"MUST INCLUDE: {c['expected'].get('must_include')}")
    print(f"PATH: {out['meta']['path']}")
    print(f"ANSWER: {p['answer'][:200]}")
    print(f"ESCALATION: {p['escalation'][:100]}")
    must = c["expected"].get("must_include", [])
    full = (p["answer"] + " " + p["escalation"]).lower()
    for w in must:
        print(f"  '{w}' found: {w.lower() in full}")
