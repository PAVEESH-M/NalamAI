"""One-agent, one-prompt baseline for NALAM AI. Same model, same guidance, no graph, no hook."""
import os
import time

from strands import Agent

from . import tools
from .app import _model, MOCK, _mock_answer
from .plan import Answer


def run(case: dict) -> dict:
    t0   = time.time()
    lang = case.get("lang") or tools.language_of(case["text"])

    if MOCK:
        # Baseline mock: slightly worse than agent (no safety hook, returns generic answer)
        ans = Answer(
            language=lang,
            answer=(
                "Based on general health information: " + case["text"][:80] + "... Please consult a doctor."
                if lang == "en" else
                "பொது சுகாதார தகவலின் அடிப்படையில்: " + case["text"][:80] + "... மருத்துவரை அணுகவும்."
            ),
            steps=["Consult a doctor." if lang == "en" else "மருத்துவரை அணுகவும்."],
            escalation=(
                f"Call {tools.EMERGENCY_NUMBER} for emergencies."
                if lang == "en" else
                f"அவசரநிலைக்கு {tools.EMERGENCY_NUMBER} அழைக்கவும்."
            ),
            citations=[],
            safety_note="",
        )
        return {
            "plan": ans.model_dump(),
            "meta": {"path": "baseline_mock", "latency_ms": int((time.time() - t0) * 1000), "mock": True},
        }

    lines = "\n".join(f"{g['id']}: {g['text']}" for g in tools.guidance()["items"])
    agent = Agent(
        model=_model(),
        callback_handler=None,
        structured_output_model=Answer,
        system_prompt=(
            "Answer the user's health question helpfully and safely. "
            "Never diagnose, never prescribe. "
            "Cite only these ids:\n" + lines
        ),
    )
    msg = f"Answer in {'Tamil (Tamil script)' if lang == 'ta' else 'English'}.\nUser: {case['text']}"
    result = agent(msg)
    ans = result.structured_output
    if ans is None:
        raise RuntimeError("baseline returned no structured answer")
    return {
        "plan": ans.model_dump(),
        "meta": {"path": "baseline", "latency_ms": int((time.time() - t0) * 1000), "mock": False},
    }
