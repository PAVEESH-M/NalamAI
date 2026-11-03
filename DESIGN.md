# NALAM AI — Design

## Strands blocks used

| Block | Where | Why |
|-------|-------|-----|
| **hooks** (BeforeNodeCallEvent) | `agent/app.py` RedFlagGate | Hard stop before any model call for emergency + clinical phrases. Code-owned. No model writes the emergency answer. |
| **graph** (planner → critic) | `agent/app.py` build_graph() | planner drafts; critic checks language, citations, no-diagnosis rule; planner revises up to 2×. Fail-closed: if critic fails, planner answer is used. |
| **structured_output** | `agent/plan.py` Answer + Critique | Enforces the output contract; scorer is deterministic. |
| **tools** | `agent/tools.py` | lookup_guidance, get_emergency_info, get_healthcare_facilities, explain_prescription_text — all read-only, curated data. |
| **swarm-ready** | architecture | backend/main.py is structured so a prescription OCR agent and a triage agent can be composed into a Swarm in a future version. |

## Safety architecture (4 rules satisfied)

1. **Code owns the facts**: emergency numbers (108, 104, 1800-116-117), HANDOFF text, and RED_FLAG phrase lists live in `agent/tools.py` as constants. The model reads them via `get_emergency_info` but cannot change them.

2. **Hard stop when someone is in danger**: `RedFlagGate` (a `HookProvider`) fires on `BeforeNodeCallEvent` and sets `event.cancel_node`. The emergency response is assembled in `agent/app.py::run()` from code-owned strings — no model call is ever made for emergency inputs.

3. **A check the model cannot skip**: the critic agent in the graph checks every planner answer for: wrong language, invalid citation ids, diagnosis language, dose advice, missing escalation. `ok=False` triggers a revision loop. If the graph fails, `run()` raises — it never silently returns an unchecked answer.

4. **Measured against a baseline**: `agent/baseline.py` is a single-agent, no-hook version. `ss measure` runs both on `cases.jsonl` and the agent must be safe on every case and score higher than the baseline.

## FastAPI backend
- `POST /api/chat` → safety gate → mock/agent → structured Answer
- `POST /api/prescription` → OCR → safety gate → explanation
- `GET /api/facilities` → static curated data
- `GET /api/emergency-info` → code-owned numbers

## React frontend
- Language toggle (EN / தமிழ்)
- Chat tab with quick prompts
- Prescription upload (drag-and-drop OCR)
- Facilities tab
- Preventive health tips
- Persistent emergency banner (108, 104)

## Mock mode
`NALAM_MOCK=1` (default) runs without AWS credentials. Every path through the safety system is exercised. Switching to live Bedrock requires only `NALAM_MOCK=0` and valid `aws configure` / `aws sso login`.
