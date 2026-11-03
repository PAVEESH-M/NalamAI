"""Structured output models for NALAM AI health assistant."""
from typing import Literal, Optional
from pydantic import BaseModel, Field


class Answer(BaseModel):
    language: Literal["en", "ta"]
    answer: str = Field(description="Plain-language answer in the user's language. Never diagnose, never prescribe, never change dosage.")
    steps: list[str] = Field(default_factory=list, description="Practical next steps the person can take, short and specific.")
    escalation: str = Field(description="When and to whom to escalate: pharmacist, doctor, emergency (108), helpline (104/1800-180-1104).")
    citations: list[str] = Field(description="Guidance ids returned by lookup_guidance that support this answer.")
    safety_note: str = Field(default="", description="Any important safety caveat, in the user's language.")


class Critique(BaseModel):
    ok: bool
    problems: list[str] = Field(default_factory=list)


class PrescriptionReading(BaseModel):
    """Result of OCR + explanation of a prescription image."""
    raw_text: str = Field(description="Raw OCR text extracted from the image.")
    medicines: list[dict] = Field(default_factory=list, description="List of {name, dose, frequency, duration} parsed from the prescription.")
    explanation: str = Field(description="Plain-language explanation of each medicine's purpose based only on lookup_guidance data.")
    warnings: list[str] = Field(default_factory=list, description="Important safety warnings about the prescription.")
    pharmacist_note: str = Field(
        default="Always verify this explanation with your pharmacist. This is not medical advice.",
        description="Mandatory note to verify with pharmacist."
    )
