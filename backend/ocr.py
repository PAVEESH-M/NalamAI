"""Prescription OCR module. Uses pytesseract (Tesseract) if available; falls back to mock."""
from __future__ import annotations

import io
import os
import re
import sys
from pathlib import Path
from typing import Optional

# Try importing PIL and pytesseract; graceful fallback if Tesseract binary not installed
try:
    from PIL import Image
    import pytesseract
    _OCR_AVAILABLE = True
except ImportError:
    _OCR_AVAILABLE = False

MOCK_OCR = os.environ.get("NALAM_MOCK", "1") == "1"

MOCK_PRESCRIPTIONS = [
    """Dr. S. Meenakshi, MBBS, MD
Government Primary Health Centre, Madurai

Patient: Ravi Kumar, Age 45, M

Rx:
1. Tab. Metformin 500mg – 1 tab twice daily after food x 90 days
2. Tab. Amlodipine 5mg – 1 tab once daily morning x 90 days
3. Tab. Atorvastatin 10mg – 1 tab once daily night x 90 days

Advice: Low salt diet, daily 30 min walk, recheck BP in 30 days.

Signature: Dr. S. Meenakshi
Date: 2026-10-28""",

    """Dr. A. Rajendran, MBBS
Apollo Clinic, Chennai

Patient: Kavitha, 32F

Rx:
1. Cap. Amoxicillin 500mg – 1 cap three times daily x 7 days (complete the course)
2. Tab. Paracetamol 500mg – 1 tab three times daily if fever, max 3 days
3. Tab. Domperidone 10mg – 1 tab before meals x 5 days

Date: 2026-11-01""",
]


def extract_text_from_image(image_bytes: bytes, filename: str = "") -> dict:
    """
    Extract text from a prescription image.
    Returns {text, method, success, error}.
    """
    if MOCK_OCR:
        # Return a plausible mock prescription
        import hashlib
        idx = int(hashlib.md5(image_bytes[:64]).hexdigest(), 16) % len(MOCK_PRESCRIPTIONS)
        return {
            "text": MOCK_PRESCRIPTIONS[idx],
            "method": "mock",
            "success": True,
            "error": None,
        }

    if not _OCR_AVAILABLE:
        return {
            "text": "",
            "method": "none",
            "success": False,
            "error": "pytesseract or PIL not installed. Install with: pip install pytesseract Pillow",
        }

    try:
        image = Image.open(io.BytesIO(image_bytes))

        # Try Tamil + English OCR first, then English-only fallback
        try:
            text = pytesseract.image_to_string(image, lang="tam+eng")
        except Exception:
            text = pytesseract.image_to_string(image, lang="eng")

        return {
            "text": text.strip(),
            "method": "tesseract",
            "success": True,
            "error": None,
        }
    except Exception as e:
        return {
            "text": "",
            "method": "tesseract",
            "success": False,
            "error": str(e),
        }


def parse_prescription_medicines(text: str) -> list[dict]:
    """Parse medicines from OCR text. Returns list of {name, dose, frequency, duration}."""
    medicines = []
    # Match common prescription patterns like:
    # Tab. Metformin 500mg - 1 tab twice daily x 90 days
    # 1. Cap. Amoxicillin 500mg - 1 cap three times daily x 7 days
    pattern = re.compile(
        r"(?:\d+\.\s*)?"                        # optional number
        r"(?:Tab|Cap|Syr|Inj|Oint|Drop)\.?\s+"  # formulation
        r"([A-Za-z\s]+?)\s+"                     # medicine name
        r"(\d+(?:\.\d+)?(?:mg|mcg|ml|g|IU))"    # dose
        r".*?(\d+\s*(?:tab|cap|ml|drop|puff|unit)\w*)"  # quantity
        r".*?(once|twice|three times|thrice|\d+\s*times)"  # frequency
        r".*?(?:x|for)?\s*(\d+\s*(?:days?|weeks?|months?))",  # duration
        re.IGNORECASE,
    )
    for m in pattern.finditer(text):
        medicines.append({
            "name": m.group(1).strip(),
            "dose": m.group(2),
            "frequency": m.group(4),
            "duration": m.group(5),
        })

    # Fallback: line-by-line parsing for simpler formats
    if not medicines:
        for line in text.splitlines():
            line = line.strip()
            if re.search(r"\b(Tab|Cap|Syr|Inj|Oint)\b", line, re.IGNORECASE):
                medicines.append({"name": line, "dose": "", "frequency": "", "duration": ""})

    return medicines[:10]  # cap at 10 items
