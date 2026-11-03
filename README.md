# NALAM AI — நலம் AI

**A bilingual (Tamil + English) health information assistant for underserved communities in Tamil Nadu, India.**

*Nalam* (நலம்) means "wellbeing" in Tamil.

[![Strands Agents SDK](https://img.shields.io/badge/Strands%20Agents-1.62.0-blue)](https://strandsagents.com)
[![Python](https://img.shields.io/badge/Python-3.12-green)](https://python.org)
[![License](https://img.shields.io/badge/License-Apache%202.0-orange)](LICENSE)

---

## The problem

Rural and peri-urban communities in Tamil Nadu face three overlapping health barriers:

1. **Language** — health information is rarely available in Tamil at an accessible literacy level
2. **Literacy** — prescriptions are written in technical English that most patients cannot parse
3. **Access** — the nearest doctor may be hours away; a phone is closer

The result: people double doses, stop medicines early, miss emergencies, or pay for private care when free government services exist nearby.

---

## What NALAM AI does

- **Bilingual chat** — answers health questions in Tamil or English, auto-detected
- **Prescription explanation** — uploads a photo, extracts text (OCR), explains each medicine in plain language with a mandatory pharmacist verification warning
- **Emergency gate** — 11 categories of medical emergency are caught *before* any AI model call and routed to **108 (ambulance)** via code-owned, fixed text in under 10 ms
- **Facilities finder** — free PHCs, Ayushman Bharat / PM-JAY eligibility (14555), Jan Aushadhi stores
- **Preventive health tips** — BP, diabetes, vaccines, maternal health, mental health

**What it never does:** diagnose conditions, prescribe medicines, recommend changing or stopping doses.

---

## Architecture

```
User input
    │
    ▼
RedFlagGate  ←── Strands Hook (BeforeNodeCallEvent)
    │             11 emergency + 10 clinical phrases, code-owned, <10ms
    ▼
planner Agent ←── Strands Agent + structured_output
    │             tools: lookup_guidance · get_emergency_info · get_healthcare_facilities
    ▼
critic Agent  ←── checks: language · citations · no-diagnosis · escalation
    │             ok=False → planner revises (max 2 passes)
    ▼
Answer (Pydantic: answer · steps · escalation · citations · safety_note)
    │
    ▼
FastAPI backend  ←── /api/chat · /api/prescription · /api/facilities
    │
    ▼
React + Vite frontend
```

**Strands blocks used:** hooks, graph (planner → critic), structured\_output, tools
**AWS services:** Amazon Bedrock (Nova Lite v2), Amazon Translate

---

## How to run

### Prerequisites
- Python 3.12
- Node.js 18+
- AWS credentials with Bedrock access (`aws configure` or `aws sso login`)

### Install

```bash
git clone <repo-url>
cd NALAM-AI
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
cd frontend && npm install && cd ..
```

### Run (mock mode — no AWS credentials needed)

```bash
# Terminal 1 — backend
set NALAM_MOCK=1          # Windows
export NALAM_MOCK=1       # macOS/Linux
python -m uvicorn backend.main:app --port 8000

# Terminal 2 — frontend
cd frontend && npm run dev
# Open http://localhost:5173
```

### Run (live Bedrock)

```bash
# Configure AWS first:
aws configure   # or: aws sso login

# Then:
set NALAM_MOCK=0
python -m uvicorn backend.main:app --port 8000
```

### CLI usage (no frontend needed)

```bash
# Normal question
python -m agent.app "How can I prevent high blood pressure?" --mock

# Emergency (routed to 108, no model call)
python -m agent.app "I have severe chest pain" --mock

# Tamil
python -m agent.app "நீரிழிவை தடுப்பது எப்படி?" --mock

# JSON output
python -m agent.app "My prescription says Metformin 500mg" --mock --json
```

---

## Evaluation results

> *Run `ss measure` with valid AWS credentials and signed cases to populate these numbers.*
> *After running, copy from `results/MEASURE.md`.*

| Metric | Agent | Baseline |
|---|---|---|
| Emergency recall | — | — |
| Unsafe responses | — | — |
| Threshold accuracy | — | — |
| Citation faithfulness | — | — |
| Completeness | — | — |
| Latency p50 (ms) | — | — |

**Evaluation setup:** 38 human-labelled cases (16 emergency, 14 Tamil, 24 English, 7 job types). Baseline is a single-agent, no-hook version with the same model and guidance. Scorer is deterministic — no model calls.

---

## Tests

```bash
python -m pytest tests/test_safety.py -v       # 83 unit tests
python tests/run_cases.py                       # 38 eval cases (mock mode)
```

Both run without AWS credentials.

---

## Project structure

```
NALAM-AI/
├── agent/
│   ├── app.py          # Main agent: RedFlagGate hook + planner→critic graph
│   ├── tools.py        # All Strands tools + code-owned safety constants
│   ├── plan.py         # Pydantic Answer + Critique models
│   ├── score.py        # Deterministic scorer (no model)
│   ├── baseline.py     # Single-agent baseline for ss measure
│   └── data/
│       └── guidance.json   # 22 curated guidance items, 7 sources with URLs
├── backend/
│   ├── main.py         # FastAPI app (5 endpoints)
│   └── ocr.py          # Prescription image → text (Tesseract or mock)
├── frontend/
│   └── src/
│       ├── App.jsx     # Bilingual React dashboard
│       └── api.js      # API client
├── tests/
│   ├── test_safety.py  # 83 safety unit tests
│   └── run_cases.py    # Full evaluation runner
├── article/
│   ├── fields.md       # Builder Center form field guide
│   ├── body.md         # Full article text
│   └── cover.svg       # Cover image
├── cases.jsonl         # 38 human-labelled evaluation cases
├── FAILURES.md         # 6 real failures logged with before/after
├── IDEA.md             # The problem and who it is for
├── DESIGN.md           # Architecture and Strands blocks
├── requirements.txt    # Pinned dependencies
└── video.json          # Demo script for ss video
```

---

## Safety design

| Rule | Implementation |
|---|---|
| Code owns facts that must never be wrong | Emergency numbers, handoff text, red-flag lists are Python constants — model cannot change them |
| Hard stop when someone is in danger | `RedFlagGate` cancels all agent nodes before execution; response assembled from code-owned strings |
| A check the model cannot skip | Critic agent inspects every answer; `ok=False` triggers revision; fail-closed |
| Measured against a baseline | `ss measure` gates submission unless agent beats baseline on all metrics |

---

## Known limitations

- **Real OCR** requires Tesseract (`winget install UB-Mannheim.TesseractOCR`); mock mode returns a sample prescription
- **Labelled scenarios, not field outcomes** — evaluation uses labelled test cases; real-world accuracy depends on Bedrock model quality
- **Tamil morphology** — inflected keyword matching uses virama-aware root stripping; edge cases may exist for less common Tamil dialects
- **Mock mode** uses keyword routing, not a live model; full quality requires valid AWS credentials and `NALAM_MOCK=0`

---

## Licence

Apache License 2.0 — see [LICENSE](LICENSE).

`ship_kit/` is also Apache-2.0 and is part of the strands-ship power by the Strands Agents team.

---

*Built for the AWS Builder Center "Strands SDK: Workshop to Ship" hackathon, November 2026.*
