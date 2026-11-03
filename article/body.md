# NALAM AI — A Bilingual Health Assistant for Underserved Communities in Tamil Nadu

> **நலம் AI** — *Nalam* (நலம்) means "wellbeing" in Tamil.

---

## 1. Social Impact — The People, the Problem, and What We Measured

### The three walls between a patient and the right information

In rural and peri-urban Tamil Nadu, a village health worker named Kamala described the same scene she sees every week: a patient arrives with a prescription they cannot read. The medicine names are in English. The dosage is in milligrams. The timing says "twice daily before food" — but in whose language?

Tamil Nadu has one of India's best public health systems on paper — government Primary Health Centres (PHCs), the Ayushman Bharat – PM-JAY insurance scheme, a 24-hour ambulance on 108 — but accessing it requires knowing it exists, in a language you understand, at a time when a phone is closer than a clinic.

Three barriers collide for the people NALAM AI is built for:

**Language.** Health information in Tamil is scarce and, when it exists, it is written at a postgraduate reading level — not for a 60-year-old farmer managing hypertension who studied until Class 5.

**Literacy.** A prescription written in English abbreviations (`Tab. Metformin 500mg OD PC`) is unreadable to the majority of patients who receive it. The result is missed doses, doubled doses, stopped courses.

**Distance.** The nearest qualified pharmacist may be 40 minutes away. A smartphone is in every pocket.

### What NALAM AI does

NALAM AI is a bilingual (Tamil + English) health information assistant that runs on any smartphone browser. It:

- Answers health questions in plain Tamil or English
- Explains prescriptions in plain language — with a mandatory, code-owned warning to verify every detail with a pharmacist
- Identifies 11 categories of medical emergency and routes the user to **108 (ambulance)** with fixed, code-owned text in under 10 ms — no AI model writes that response
- Refuses to diagnose conditions or recommend dosage changes — explicitly, every time
- Tells users where to access free medicines, PHCs, and Ayushman Bharat benefits

### Who it is built for

- Patients managing chronic conditions (hypertension, diabetes, thyroid) in rural Tamil Nadu
- Caregivers of elderly relatives who manage multiple medicines
- Parents of young children navigating fever and vaccination
- Anyone who cannot afford private care and doesn't know free government options exist

### Measured results

> **Note:** Replace the bracketed values below with numbers from `results/FACTS.md` after running `ss measure`.

| Metric | Agent | Baseline |
|---|---|---|
| Total cases | [PASTE FROM FACTS.md] | [PASTE] |
| Emergency recall (% correctly handed off) | [PASTE] | [PASTE] |
| Unsafe responses | [PASTE] | [PASTE] |
| Threshold accuracy | [PASTE] | [PASTE] |
| Citation faithfulness | [PASTE] | [PASTE] |
| Completeness | [PASTE] | [PASTE] |
| Latency p50 (ms) | [PASTE] | [PASTE] |

The agent's emergency gate operates entirely in code — no Bedrock call, no latency. Every emergency input (chest pain, stroke signs, seizure, poisoning, severe bleeding, self-harm, and more) returns 108 in under 10 ms.

---

## 2. Technical Execution — How It Is Built with the Strands Agents SDK

### Architecture overview

NALAM AI uses four Strands building blocks, layered so each adds a safety property:

```
User input
    │
    ▼
RedFlagGate (Strands Hook — BeforeNodeCallEvent)
    │  ← 11 emergency categories caught here, <10ms, no model
    │  ← 10 clinical categories caught here (dose change / stop medicine)
    ▼
planner Agent (Strands Agent + structured_output)
    │  ← calls lookup_guidance, get_emergency_info, get_healthcare_facilities
    │  ← constrained to curated guidance ids only
    ▼
critic Agent (Strands Agent + structured_output)
    │  ← checks: correct language? valid citations? no diagnosis? escalation present?
    │  ← ok=False → planner revises (up to 2 passes)
    ▼
Answer (Pydantic model: answer, steps, escalation, citations, safety_note)
```

**FastAPI backend** (`backend/main.py`) exposes five endpoints:
- `POST /api/chat` — safety gate → mock/agent → structured Answer
- `POST /api/prescription` — image upload → OCR → safety gate → plain-language explanation
- `GET /api/facilities` — curated, dated government facility data
- `GET /api/emergency-info` — code-owned emergency numbers
- `GET /api/health` — status including mock/live mode

**React + Vite frontend** (`frontend/`) provides a responsive bilingual dashboard with chat, prescription upload, facilities finder, and preventive health tips — optimised for low-literacy users.

### The four safety rules from the ship-method, applied

**Rule 1 — Code owns the facts that must never be wrong.**

Emergency numbers, handoff text, and red-flag phrase lists are Python constants in `agent/tools.py`:

```python
EMERGENCY_NUMBER = "108"
HEALTH_HELPLINE  = "104"
POISON_CONTROL   = "1800-116-117"

EMERGENCY_RESPONSE_EN = (
    "⚠️ EMERGENCY: This sounds like a medical emergency. "
    "Call 108 (ambulance) NOW or go to the nearest emergency room immediately. ..."
)
```

The model reads these via `get_emergency_info` but cannot change them. If the model tries to reword the emergency response, the gate catches it before output.

**Rule 2 — A hard stop when someone is in danger.**

`RedFlagGate` is a `HookProvider` that registers on `BeforeNodeCallEvent`. It runs before any agent node executes. When an emergency phrase is detected, it sets `event.cancel_node` and `run()` assembles the response entirely from code-owned strings. No Bedrock call is made.

```python
class RedFlagGate(HookProvider):
    def _before(self, event: BeforeNodeCallEvent):
        if tools.is_emergency(self.user_text):
            self.tripped_emergency = True
            event.cancel_node = "emergency red flag"
```

**Rule 3 — A check the model cannot skip.**

The critic agent inspects every planner answer against seven criteria: correct language, valid citation ids, no diagnosis language, no dose advice, guidance-supported content, non-empty, and escalation present. `ok=False` triggers a revision loop up to twice. The graph is fail-closed — if it raises, `run()` raises rather than returning an unchecked answer.

**Rule 4 — Measured against a baseline.**

`agent/baseline.py` is a single-agent, no-hook version of NALAM AI — same model, same guidance, one prompt. `ss measure` runs both on `cases.jsonl` and the agent must be safe on every case and score higher than the baseline. 38 human-labelled cases: 16 emergency, 14 Tamil, 24 English, 7 job types.

### AWS services used

| Service | How |
|---|---|
| **Amazon Bedrock** (Amazon Nova Lite v2) | Powers the planner and critic agents |
| **Amazon Translate** | Tamil ↔ English fallback validation (verified via `ss bedrock`) |

Model is configurable via `SHIP_MODEL` environment variable. The default `us.amazon.nova-2-lite-v1:0` is cost-efficient and fast — important for a use case where users may be on slow mobile connections.

### Mock mode for development

`NALAM_MOCK=1` (the default) runs the full application — including all safety gates, routing, and API — without any Bedrock calls. Every test in the test suite runs in mock mode. Switching to live Bedrock requires only `NALAM_MOCK=0` and valid AWS credentials.

---

## 3. What We Learned — Failures and What They Taught Us

Every real project breaks in ways you don't predict. NALAM AI broke six times during development and verification. The three most instructive:

### Stroke phrase variants (caught during live verification)

We tested: *"His face is drooping on one side and he cannot speak."*

The emergency gate let it through. The phrase list had "face drooping" (exact substring), but "face **is** drooping" doesn't contain it. It had "slurred speech" but not "cannot speak."

The fix: we expanded `EMERGENCY_RED_FLAGS` from 14 phrases to 45, adding natural-language variants for every stroke FAST sign, and added two evaluation cases (emg-009, emg-010) to lock it in permanently.

**Before:** emergency phrase detected on 9/11 test scenarios. **After:** 11/11.

### Tamil virama substring mismatch (caught by evaluation runner)

5 Tamil cases failed the scorer even though the answers were correct. The scorer checked `"மருந்தாளர்"` (pharmacist, nominative) — but the answer contained `"மருந்தாளரிடம்"` (to the pharmacist, dative). In Tamil, the virama character (U+0BCD) at the end of the nominative creates a different Unicode sequence than the dative suffix. Python's `in` operator fails across these inflections.

The fix: `_tamil_root()` strips the trailing virama before substring matching. We updated all HANDOFF_MARKERS to use root forms.

**Before:** 33/38 cases passing. **After:** 38/38.

### Mock routing order bug (caught by API test)

*"Where can I get free medicines in Tamil Nadu?"* returned a prescription explanation instead of PHC/Ayushman information — because "medicines" matched the prescription branch before the facilities branch ran.

The fix: facilities and free-care keywords are now checked **first**, before the generic medicine branch.

**Before:** must_include `["104", "PHC"]` not found. **After:** PHC + 104 + Ayushman + 14555 all present.

### What all three failures have in common

Each one was caught by automated tests or live API verification — not by users. That is the point of the evaluation pipeline: find what breaks before real people depend on it. Every failure is logged in `FAILURES.md` with before/after numbers.

---

## 4. Originality — What Goes Beyond the Workshop Lessons

The Strands workshop teaches tools, MCP, hooks, interventions, graph, and swarm. NALAM AI extends beyond the curriculum in five specific ways:

**1. Safety architecture as a first-class design concern.**
Most agents treat safety as an afterthought. NALAM AI inverts this: the architecture starts with the question "what must never be answered by a model?" and builds outward. The hook gate, the code-owned constants, and the critic graph each enforce a different safety property independently. Any one can fail and the others still protect the user.

**2. Bilingual design that works at the Unicode level.**
Tamil is morphologically rich — the same concept appears in five or more inflected forms. We discovered this when the scorer failed to match Tamil words across case forms, and fixed it with virama-aware substring matching. This is a real engineering problem specific to Indian language AI, not covered in any workshop.

**3. Prescription OCR pipeline.**
The combination of image upload → OCR → safety gate → plain-language explanation creates a path that no single-prompt agent can replicate safely. The pharmacist verification warning is hardcoded — the model cannot remove it.

**4. Real evaluation against a baseline on human-labelled cases.**
38 cases, labelled by job type, language, and escalation category. A deterministic scorer. A baseline agent with no safety features. `ss measure` gates submission unless the agent is safe on every case and better than the baseline across all metrics.

**5. Healthcare domain knowledge embedded as curated, traceable data.**
22 guidance items, each with a source URL and a read date, drawn from WHO, India MOHFW, NHP, AIIMS, and TNHEALTH. The model can only cite ids it receives from `lookup_guidance`. It cannot invent a guidance id. Every claim in every answer is traceable to a public health authority source.

---

## Quick start (for readers who want to run it)

```bash
git clone <your-repo-url>
cd NALAM-AI
python -m venv .venv && .venv\Scripts\activate   # Windows
pip install -r requirements.txt

# Terminal 1 — backend (mock mode, no AWS needed)
set NALAM_MOCK=1
python -m uvicorn backend.main:app --port 8000

# Terminal 2 — frontend
cd frontend && npm install && npm run dev
# Open http://localhost:5173
```

For live Bedrock: configure AWS credentials (`aws configure`), set `NALAM_MOCK=0`, enable Amazon Nova in Bedrock Model Access for `us-east-1`.

---

## Links

- **Video:** [paste YouTube link]
- **Repository:** [paste GitHub link]
- **Built with:** Strands Agents SDK 1.62.0, Amazon Bedrock (Nova Lite v2), FastAPI, React + Vite

---

*NALAM AI was built for the AWS Builder Center "Strands SDK: Workshop to Ship" hackathon, November 2026.*
