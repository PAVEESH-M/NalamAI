"""NALAM AI tools. Read-only, curated sources only. Code owns all safety-critical facts."""
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Optional

from strands import tool

DATA = Path(__file__).parent / "data"
TAMIL = re.compile(r"[\u0B80-\u0BFF]")

# ── Safety facts owned by code, never by the model ────────────────────────────
EMERGENCY_NUMBER = "108"        # India ambulance
HEALTH_HELPLINE  = "104"        # Tamil Nadu / national health advice
NATIONAL_HEALTH  = "1800-180-1104"
POISON_CONTROL   = "1800-116-117"
MENTAL_HEALTH    = "9152987821"  # iCall

EMERGENCY_RESPONSE_EN = (
    "⚠️ EMERGENCY: This sounds like a medical emergency. "
    f"Call {EMERGENCY_NUMBER} (ambulance) NOW or go to the nearest emergency room immediately. "
    "Do not wait. This assistant cannot help with emergencies."
)
EMERGENCY_RESPONSE_TA = (
    "⚠️ அவசரநிலை: இது ஒரு மருத்துவ அவசரநிலையாக தோன்றுகிறது. "
    f"இப்போதே {EMERGENCY_NUMBER} (ஆம்புலன்ஸ்) அழைக்கவும் அல்லது உடனே அருகில் உள்ள "
    "அவசர சிகிச்சை பிரிவிற்கு செல்லவும். காத்திருக்காதீர்கள். "
    "இந்த உதவியாளர் அவசரநிலைகளில் உதவ முடியாது."
)
HANDOFF_EN = (
    "This question needs a qualified healthcare professional. "
    "Please consult your doctor or pharmacist. "
    f"For urgent concerns call the health helpline: {HEALTH_HELPLINE}."
)
HANDOFF_TA = (
    "இந்தக் கேள்விக்கு தகுதியான சுகாதார நிபுணரின் உதவி தேவை. "
    "உங்கள் மருத்துவர் அல்லது மருந்தாளரிடம் கலந்தாலோசிக்கவும். "
    f"அவசர தேவைகளுக்கு சுகாதார உதவி எண்: {HEALTH_HELPLINE}."
)
NEVER_DIAGNOSE_EN = "I cannot diagnose medical conditions. Please see a doctor for a proper diagnosis."
NEVER_DIAGNOSE_TA = "என்னால் மருத்துவ நிலைமைகளை கண்டறிய முடியாது. சரியான கண்டறிதலுக்கு மருத்துவரை அணுகவும்."

# ── Red-flag phrases that trigger immediate handoff ───────────────────────────
# Code owns this list; the model cannot bypass it.
EMERGENCY_RED_FLAGS = [
    # English — chest / cardiac
    "chest pain", "chest tightness", "chest pressure", "heart attack",
    "my heart", "heart is racing", "heart is pounding",
    # English — breathing
    "cannot breathe", "can't breathe", "difficulty breathing",
    "shortness of breath", "trouble breathing", "hard to breathe",
    "not able to breathe", "unable to breathe", "gasping",
    "lips are blue", "lips turning blue", "fingernails blue",
    # English — stroke (FAST)
    "stroke", "face drooping", "face is drooping", "face dropped",
    "face falling", "one side of face", "facial droop",
    "arm weakness", "arm is weak", "arm went numb", "sudden numbness",
    "slurred speech", "cannot speak", "can't speak", "speech is slurred",
    "sudden confusion", "sudden severe headache",
    # English — unconscious / unresponsive
    "unconscious", "unresponsive", "not responding", "passed out",
    "collapsed", "fainted", "won't wake up", "cannot wake",
    "not breathing", "stopped breathing", "no pulse",
    # English — seizure
    "seizure", "convulsion", "convulsing", "fitting", "shaking uncontrollably",
    "jerking", "epilepsy attack",
    # English — bleeding
    "severe bleeding", "heavy bleeding", "bleeding won't stop",
    "bleeding a lot", "blood won't stop", "uncontrolled bleeding",
    # English — poisoning / overdose
    "poisoning", "overdose", "swallowed poison", "took too many pills",
    "took an overdose", "ingested poison", "drank poison",
    # English — self-harm
    "suicide", "kill myself", "end my life", "take my life",
    "want to die", "harm myself",
    # Tamil
    "நெஞ்சு வலி", "மூச்சு திணறல்", "மூச்சு வர", "மாரடைப்பு",
    "இதயம்", "பக்கவாதம்", "முகம் தொங்க", "கை வலுவற்ற",
    "பேச முடியாத", "வலிப்பு", "மயக்கம்", "உணர்வற்ற",
    "அதிகமாக மாத்திரை", "விஷம்", "தற்கொலை",
    "இரத்தம் நிறுத்த", "கடுமையான இரத்தம்", "நிறுத்த முடியாத",
]

# Phrases that require pharmacist/doctor handoff (not 108 emergency)
CLINICAL_RED_FLAGS = [
    # English
    "double the dose", "double my dose", "extra dose", "skip the dose",
    "stop taking", "stop my medicine", "change my dose", "change the dose",
    "increase my dose", "decrease my dose", "can i stop",
    "what dose should i take", "how much should i take",
    # Tamil — include verb conjugation variants
    "இரட்டிப்பு மாத்திரை", "மாத்திரை நிறுத்த", "அளவை மாற்ற",
    "எவ்வளவு மாத்திரை", "மாத்திரை அளவு",
    "மாத்திரை அளவை மாற்ற",  # "மாற்றலாமா" starts with "மாற்ற"
    "மருந்தை நிறுத்த", "மருந்து நிறுத்த",
    "அளவை அதிகரிக்க", "அளவை குறைக்க",
]


@lru_cache(maxsize=1)
def guidance():
    return json.loads((DATA / "guidance.json").read_text(encoding="utf-8"))


def guidance_ids() -> set:
    return {g["id"] for g in guidance()["items"]}


def language_of(text: str) -> str:
    return "ta" if TAMIL.search(text or "") else "en"


def has_tamil(text: str) -> bool:
    return bool(TAMIL.search(text or ""))


def is_emergency(text: str) -> bool:
    """Return True if text contains any emergency red-flag phrase."""
    lower = text.lower()
    return any(flag.lower() in lower for flag in EMERGENCY_RED_FLAGS)


def needs_clinical_handoff(text: str) -> bool:
    """Return True if text contains a clinical red-flag (dose change etc.)."""
    lower = text.lower()
    return any(flag.lower() in lower for flag in CLINICAL_RED_FLAGS)


def emergency_response(lang: str) -> str:
    """Return fixed, code-owned emergency response text. Model cannot change this."""
    return EMERGENCY_RESPONSE_TA if lang == "ta" else EMERGENCY_RESPONSE_EN


def handoff_response(lang: str) -> str:
    """Return fixed clinical handoff response. Model cannot change this."""
    return HANDOFF_TA if lang == "ta" else HANDOFF_EN


# ── Strands tools (called by the agent) ───────────────────────────────────────

@tool
def lookup_guidance(topic: str) -> list[dict]:
    """Find curated, dated health guidance to cite. Returns items with id and text.

    Only call this tool. Never invent guidance or cite ids not returned here.

    Args:
        topic: words describing what the user needs (e.g. "chest pain emergency", "blood pressure prevention")
    """
    words = [w for w in re.findall(r"\w+", topic.lower()) if len(w) > 2]
    items = guidance()["items"]
    hits = [g for g in items if any(w in (g["id"] + " " + g["text"]).lower() for w in words)]
    return [{"id": g["id"], "text": g["text"]} for g in (hits or items)[:6]]


@tool
def get_emergency_info(lang: str = "en") -> dict:
    """Return code-owned emergency contact numbers and fixed response text.

    Call this whenever emergency or urgent escalation is needed.

    Args:
        lang: "en" for English or "ta" for Tamil
    """
    return {
        "ambulance": EMERGENCY_NUMBER,
        "health_helpline": HEALTH_HELPLINE,
        "national_helpline": NATIONAL_HEALTH,
        "poison_control": POISON_CONTROL,
        "mental_health_helpline": MENTAL_HEALTH,
        "emergency_message": EMERGENCY_RESPONSE_TA if lang == "ta" else EMERGENCY_RESPONSE_EN,
    }


@tool
def get_healthcare_facilities(location: str = "Tamil Nadu") -> list[dict]:
    """Return information about healthcare facilities near the user's location.

    Args:
        location: city or state name in India (default Tamil Nadu)
    """
    # Curated static data — verified against public sources 2026-11-01
    facilities = [
        {
            "name": "Government Primary Health Centre (PHC)",
            "type": "primary_care",
            "services": "Free outpatient care, basic medicines, vaccinations, maternal health",
            "hours": "Monday–Saturday, 8 AM – 2 PM",
            "cost": "Free",
            "how_to_find": "Call 104 (Tamil Nadu health helpline) for nearest PHC",
        },
        {
            "name": "Government District Hospital",
            "type": "secondary_care",
            "services": "Specialist outpatient, emergency, surgery, diagnostics",
            "hours": "24 hours emergency; OPD Monday–Saturday 8 AM–1 PM",
            "cost": "Free / subsidised",
            "how_to_find": "Available in every district headquarter in Tamil Nadu",
        },
        {
            "name": "Ayushman Bharat – PM-JAY empanelled hospital",
            "type": "secondary_tertiary",
            "services": "Hospitalisation cover up to ₹5 lakh/family/year for eligible families",
            "hours": "Varies by hospital",
            "cost": "Free for eligible beneficiaries",
            "how_to_find": "Call 14555 to check eligibility and find nearest empanelled hospital",
        },
        {
            "name": "TNMSC Jan Aushadhi Kendra (generic medicine store)",
            "type": "pharmacy",
            "services": "Quality generic medicines at 50-90% lower cost than branded versions",
            "hours": "Typically 9 AM – 6 PM",
            "cost": "Low cost",
            "how_to_find": "Available at district hospitals and select PHCs in Tamil Nadu",
        },
    ]
    return facilities


@tool
def explain_prescription_text(prescription_text: str, lang: str = "en") -> dict:
    """Provide plain-language explanation of extracted prescription text.

    IMPORTANT: Always includes mandatory pharmacist verification warning.
    Never invent instructions not present in the text.

    Args:
        prescription_text: OCR-extracted text from a prescription image
        lang: "en" or "ta"
    """
    warning_en = (
        "⚠️ IMPORTANT: This is an AI explanation only. "
        "Always verify every detail—medicine name, dose, frequency, and duration—"
        "directly with your dispensing pharmacist before taking any medicine. "
        "Never change your dose based on this explanation."
    )
    warning_ta = (
        "⚠️ முக்கியம்: இது AI விளக்கம் மட்டுமே. "
        "மாத்திரை பெயர், அளவு, எத்தனை முறை, எத்தனை நாள் என்பதை "
        "மருந்தாளரிடம் நேரடியாக சரிபார்க்கவும். "
        "இந்த விளக்கத்தின் அடிப்படையில் அளவை மாற்றாதீர்கள்."
    )
    return {
        "raw_text": prescription_text,
        "pharmacist_warning": warning_ta if lang == "ta" else warning_en,
        "guidance_context": lookup_guidance._tool_func("prescription medicine dose instructions"),
    }
