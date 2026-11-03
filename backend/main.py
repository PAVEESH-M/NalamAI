"""NALAM AI – FastAPI backend.

    python -m backend.main          # starts on http://localhost:8000
    NALAM_MOCK=1 python -m backend.main   # default: mock mode, no AWS needed

Endpoints:
    POST /api/chat              { text, lang? }  →  { answer, steps, escalation, citations, safety_note, meta }
    POST /api/prescription      multipart: file  →  { raw_text, medicines, explanation, warnings, pharmacist_note }
    GET  /api/health            →  { status, mock, model }
    GET  /api/facilities        →  [ { name, type, services, hours, cost, how_to_find } ]
    GET  /api/emergency-info    →  { ambulance, helpline, ... }
"""
from __future__ import annotations

import os
import sys
import logging
from pathlib import Path
from typing import Optional

# Add project root to path so `agent` package is importable
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel

# ── Import agent modules ───────────────────────────────────────────────────────
from agent import tools
from agent.app import run as agent_run
from backend.ocr import extract_text_from_image, parse_prescription_medicines

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("nalam")

app = FastAPI(
    title="NALAM AI",
    description="Tamil & English health assistant for underserved communities",
    version="1.0.0",
)

# Allow Vite dev server (port 5173) and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:4173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

MOCK = os.environ.get("NALAM_MOCK", "1") == "1"


# ── Request/Response models ────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    text: str
    lang: Optional[str] = None   # "en" or "ta"; auto-detected if absent


class ChatResponse(BaseModel):
    answer: str
    steps: list[str]
    escalation: str
    citations: list[str]
    safety_note: str
    language: str
    meta: dict


class PrescriptionResponse(BaseModel):
    raw_text: str
    medicines: list[dict]
    explanation: str
    warnings: list[str]
    pharmacist_note: str
    ocr_method: str


# ── Routes ─────────────────────────────────────────────────────────────────────

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "mock": MOCK,
        "model": os.environ.get("SHIP_MODEL", "us.amazon.nova-2-lite-v1:0"),
        "region": os.environ.get("AWS_REGION", "us-east-1"),
        "version": "1.0.0",
    }


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="text must not be empty")

    text = req.text.strip()

    # Truncate to reasonable length
    if len(text) > 2000:
        text = text[:2000]

    try:
        result = agent_run({"text": text, "lang": req.lang})
    except Exception as e:
        logger.error(f"agent error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)[:200]}")

    plan = result["plan"]
    return ChatResponse(
        answer=plan["answer"],
        steps=plan.get("steps", []),
        escalation=plan.get("escalation", ""),
        citations=plan.get("citations", []),
        safety_note=plan.get("safety_note", ""),
        language=plan.get("language", "en"),
        meta=result["meta"],
    )


@app.post("/api/prescription", response_model=PrescriptionResponse)
async def prescription(file: UploadFile = File(...)):
    # Validate file type
    allowed = {"image/jpeg", "image/png", "image/webp", "image/gif", "image/tiff"}
    if file.content_type and file.content_type not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {file.content_type}. Upload a JPEG or PNG image."
        )

    image_bytes = await file.read()
    if len(image_bytes) > 10 * 1024 * 1024:  # 10 MB limit
        raise HTTPException(status_code=413, detail="Image too large. Maximum size is 10 MB.")

    # OCR
    ocr_result = extract_text_from_image(image_bytes, filename=file.filename or "")
    raw_text = ocr_result["text"]

    if not ocr_result["success"]:
        raise HTTPException(status_code=422, detail=f"OCR failed: {ocr_result['error']}")

    if not raw_text.strip():
        raise HTTPException(status_code=422, detail="No text could be extracted from the image. Please upload a clear photo of the prescription.")

    # Parse medicines
    medicines = parse_prescription_medicines(raw_text)

    # Generate plain-language explanation via agent (routes through safety layer)
    explanation_prompt = (
        f"Explain this prescription in plain language. "
        f"Tell the patient what each medicine is generally used for, based only on your guidance. "
        f"Always remind them to verify with their pharmacist.\n\nPrescription:\n{raw_text[:1000]}"
    )
    lang = tools.language_of(raw_text) or "en"

    try:
        result = agent_run({"text": explanation_prompt, "lang": lang})
        explanation = result["plan"]["answer"]
    except Exception as e:
        logger.error(f"prescription explanation error: {e}")
        explanation = (
            "I was unable to generate an explanation. Please ask your pharmacist to explain each medicine."
            if lang == "en" else
            "விளக்கம் உருவாக்க முடியவில்லை. மருந்தாளரிடம் விரிவாக கேளுங்கள்."
        )

    # Fixed warnings — code-owned, not generated by model
    warnings = [
        "⚠️ This is an AI reading of your prescription image. The text may contain OCR errors.",
        "⚠️ ALWAYS verify every medicine name, dose, and timing with your pharmacist before taking.",
        "⚠️ Never change your dose based on this explanation.",
        "⚠️ If you have side effects (rash, difficulty breathing, swelling), contact your doctor immediately.",
    ]

    pharmacist_note = (
        "This explanation is for information only. Your pharmacist is the right person to "
        "confirm your medicine names, doses, and any interactions. Call 104 for free health advice."
    )

    return PrescriptionResponse(
        raw_text=raw_text,
        medicines=medicines,
        explanation=explanation,
        warnings=warnings,
        pharmacist_note=pharmacist_note,
        ocr_method=ocr_result["method"],
    )


@app.get("/api/facilities")
def facilities():
    return tools.get_healthcare_facilities._tool_func("Tamil Nadu")


@app.get("/api/emergency-info")
def emergency_info(lang: str = "en"):
    return tools.get_emergency_info._tool_func(lang=lang)


# ── Serve React build (production) ────────────────────────────────────────────
_frontend_dist = Path(__file__).resolve().parents[1] / "frontend" / "dist"
if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        index = _frontend_dist / "index.html"
        return FileResponse(str(index))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    logger.info(f"Starting NALAM AI backend on port {port} (mock={MOCK})")
    uvicorn.run("backend.main:app", host="0.0.0.0", port=port, reload=True)
