"""NALAM AI – Tamil & English health assistant.

    python -m agent.app "your question"
    python -m agent.app "your question" --json
    python -m agent.app "your question" --mock   # no Bedrock needed

Architecture (Strands blocks used):
  - RedFlagGate hook  → hard stop before any model call (safety rule 2)
  - planner → critic graph  → structured Answer (rules 1, 3)
  - lookup_guidance, get_emergency_info, get_healthcare_facilities, explain_prescription_text
  - MOCK mode for development without AWS credentials
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time

from strands import Agent
from strands.hooks import BeforeNodeCallEvent, HookProvider, HookRegistry
from strands.models import BedrockModel
from strands.multiagent import GraphBuilder

from . import tools
from .plan import Answer, Critique

MODEL_ID = os.environ.get("SHIP_MODEL", "us.amazon.nova-2-lite-v1:0")
REGION   = os.environ.get("AWS_REGION", "us-east-1")
MOCK     = os.environ.get("NALAM_MOCK", "1") == "1"   # Default ON until AWS credentials available

logging.getLogger("strands").setLevel(logging.CRITICAL)

GOAL = (
    "You are NALAM AI, a Tamil and English health assistant for underserved communities in Tamil Nadu, India. "
    "Answer only in {lang} (en = English, ta = Tamil script). "
    "You MUST call lookup_guidance first. Cite only ids it returns. "
    "Never diagnose. Never prescribe. Never recommend changing doses. "
    "If any step involves a medicine dose, always tell the user to verify with their pharmacist. "
    "Use short, plain sentences appropriate for people with limited health literacy."
)

PLANNER = GOAL + " Fix every problem a critic lists. Be concise and warm."
CRITIC  = (
    "Reply ok=false with one line per problem if the answer: "
    "(a) is not entirely in {lang}, "
    "(b) cites a guidance id not in {ids}, "
    "(c) diagnoses or prescribes medicines, "
    "(d) recommends changing a dose, "
    "(e) gives advice not supported by the cited guidance, "
    "(f) is empty, or "
    "(g) does not include an escalation path. "
    "Otherwise ok=true."
)


# ── Red-flag hook: code-owned hard stop, runs before any agent node ────────────
class RedFlagGate(HookProvider):
    """Intercepts every agent node invocation and blocks if emergency/clinical flags detected."""

    def __init__(self, user_text: str, lang: str):
        self.user_text = user_text
        self.lang = lang
        self.tripped_emergency = False
        self.tripped_clinical  = False

    def register_hooks(self, registry: HookRegistry, **_):
        registry.add_callback(BeforeNodeCallEvent, self._before)

    def _before(self, event: BeforeNodeCallEvent):
        text = self.user_text
        if tools.is_emergency(text):
            self.tripped_emergency = True
            event.cancel_node = "emergency red flag"
        elif tools.needs_clinical_handoff(text):
            self.tripped_clinical = True
            event.cancel_node = "clinical handoff required"


def _model():
    return BedrockModel(model_id=MODEL_ID, region_name=REGION, temperature=0.2)


def _mock_answer(case: dict, lang: str) -> Answer:
    """Return a realistic mock answer when NALAM_MOCK=1 (no Bedrock needed).

    Routing order matters: more-specific checks come first so that
    "where can I get free medicines" hits the facilities branch, not the
    generic prescription/medicine branch.
    """
    text = case["text"].lower()

    # ── 1b. Vaccines / immunisation ─────────────────────────────────────────
    if any(w in text for w in [
        "vaccine", "vaccination", "immunis", "immuniz", "jab", "inject",
        "தடுப்பூசி", "தடுப்பு மருந்து",
    ]):
        return Answer(
            language=lang,
            answer=(
                "India's Universal Immunisation Programme (UIP) provides free vaccines for children at government PHCs. "
                "The schedule includes BCG, Polio, DPT, Hepatitis B, Measles, and more. "
                "Your doctor or PHC nurse will guide you on which vaccines are due. "
                "Call 104 to find your nearest PHC for free vaccination."
                if lang == "en" else
                "இந்தியாவின் தடுப்பூசி திட்டம் (UIP) அரசு PHC-களில் இலவசமாக தடுப்பூசி வழங்குகிறது. "
                "BCG, போலியோ, DPT, ஹெபடைட்டிஸ் B, தட்டம்மை தடுப்பூசிகள் அடங்கும். "
                "உங்கள் மருத்துவர் அல்லது PHC செவிலியர் எந்த தடுப்பூசி எப்போது என்று கூறுவார். "
                "அருகில் உள்ள PHC கண்டுபிடிக்க 104 அழைக்கவும்."
            ),
            steps=[
                "Visit your nearest government PHC for free vaccination (call 104 to find it).",
                "Bring your child's immunisation card to track vaccines given.",
                "Adults: keep tetanus booster up to date; ask your doctor about flu vaccine.",
            ] if lang == "en" else [
                "இலவச தடுப்பூசிக்கு அருகில் உள்ள அரசு PHC-க்கு செல்லுங்கள் (104 அழைக்கவும்).",
                "குழந்தையின் தடுப்பூசி அட்டவணை கார்டு கொண்டு வாருங்கள்.",
                "பெரியவர்கள்: தனுவாத தடுப்பூசி புதுப்பிக்கவும்.",
            ],
            escalation=(
                f"Call 104 for nearest vaccination centre. Emergencies: {tools.EMERGENCY_NUMBER}."
                if lang == "en" else
                f"தடுப்பூசி மையம்: 104. அவசரநிலை: {tools.EMERGENCY_NUMBER}."
            ),
            citations=["G-PREV-VACCINE", "G-FACILITY-TN-EMG"],
            safety_note="",
        )

    # ── 1. Facilities / free care — checked BEFORE generic "medicine" ─────────
    if any(w in text for w in [
        "free medicine", "free treatment", "free care", "government hospital",
        "phc", "primary health", "ayushman", "pm-jay", "pmjay", "jan aushadhi",
        "subsidised", "affordable", "where to get", "where can i get", "get free",
        "cannot afford", "can't afford", "government help", "government scheme",
        "insurance", "health scheme", "ration card",
        "இலவச மருந்து", "இலவச சிகிச்சை", "அரசு மருத்துவமனை", "ஆரம்ப சுகாதார",
        "ஆயுஷ்மான்",
    ]):
        return Answer(
            language=lang,
            answer=(
                "Tamil Nadu has several free and affordable healthcare options:\n"
                "• Government PHCs (Primary Health Centres) provide free outpatient care Mon–Sat 8AM–2PM. "
                "Call 104 to find your nearest one.\n"
                "• Government District Hospitals offer free specialist care and emergency services 24 hours.\n"
                "• Ayushman Bharat – PM-JAY covers hospitalisation up to ₹5 lakh per family per year. "
                "Call 14555 to check eligibility.\n"
                "• Jan Aushadhi Kendras at district hospitals sell generic medicines at 50–90% lower cost."
                if lang == "en" else
                "தமிழ்நாட்டில் இலவச மற்றும் மலிவான சுகாதார வசதிகள்:\n"
                "• அரசு PHC – திங்கள்–சனி காலை 8–2 மணி, இலவசம். அருகில் PHC கண்டுபிடிக்க 104 அழைக்கவும்.\n"
                "• அரசு மாவட்ட மருத்துவமனைகள் – இலவச சிறப்பு சிகிச்சை, 24 மணி அவசர சேவை.\n"
                "• ஆயுஷ்மான் பாரத் – PM-JAY – ஒரு குடும்பத்திற்கு ₹5 லட்சம் கவரேஜ். தகுதி: 14555."
            ),
            steps=[
                "Call 104 (Tamil Nadu health helpline) to find your nearest free PHC.",
                "Bring your Aadhaar card to access Ayushman Bharat benefits.",
                "Ask at your district hospital for the Jan Aushadhi generic medicine counter.",
            ] if lang == "en" else [
                "அருகில் உள்ள இலவச PHC கண்டுபிடிக்க 104 அழைக்கவும்.",
                "ஆயுஷ்மான் பாரத் சேவைகளுக்கு ஆதார் கார்டு கொண்டு வாருங்கள்.",
                "மாவட்ட மருத்துவமனையில் Jan Aushadhi மாத்திரை கவுண்டர் கேளுங்கள்.",
            ],
            escalation=(
                f"For health information call 104. For emergencies call {tools.EMERGENCY_NUMBER}."
                if lang == "en" else
                f"சுகாதார தகவலுக்கு 104 அழைக்கவும். அவசரநிலைக்கு {tools.EMERGENCY_NUMBER} அழைக்கவும்."
            ),
            citations=["G-FACILITY-TN-EMG", "G-FACILITY-NATION"],
            safety_note="",
        )

    # ── 2. Prescription / medicine ────────────────────────────────────────────
    if any(w in text for w in [
        "prescription", "மருந்து சீட்டு", "tablet", "medicine", "மாத்திரை",
        "what does", "what is this medicine", "என் மருந்து",
    ]):
        return Answer(
            language=lang,
            answer=(
                "Your prescription shows a medicine your doctor has chosen for you. "
                "Each medicine has a specific dose and timing printed on the prescription. "
                "Always ask your pharmacist to explain each medicine in detail before you start taking it."
                if lang == "en" else
                "உங்கள் மருந்து சீட்டில் உங்கள் மருத்துவர் தேர்ந்தெடுத்த மருந்துகள் உள்ளன. "
                "ஒவ்வொரு மருந்துக்கும் குறிப்பிட்ட அளவு மற்றும் நேரம் உள்ளது. "
                "மாத்திரை எடுக்கும் முன் மருந்தாளரிடம் விரிவாக கேட்கவும். "
                "உங்கள் மருத்துவர் சொன்னபடி மட்டுமே எடுக்கவும்."
            ),
            steps=[
                "Take your prescription to the pharmacist.",
                "Ask them to explain each medicine, dose, and timing.",
                "Do not skip doses or stop the medicine without asking your doctor.",
            ] if lang == "en" else [
                "மருந்து சீட்டை மருந்தாளரிடம் கொண்டு செல்லுங்கள்.",
                "ஒவ்வொரு மருந்தின் அளவு மற்றும் நேரத்தை விளக்கும்படி கேளுங்கள்.",
                "மருத்துவரிடம் கேட்காமல் மாத்திரை நிறுத்தாதீர்கள்.",
            ],
            escalation=(
                "If you have side effects (rash, swelling, difficulty breathing), call your doctor immediately. "
                "Store medicines as directed on the label—many need a cool, dry place. "
                "Your pharmacist can also check for interactions between multiple medicines."
                if lang == "en" else
                "பக்க விளைவுகள் (தடிப்பு, வீக்கம், மூச்சு திணறல்) இருந்தால் உடனே மருத்துவரை அணுகுங்கள். "
                "மருந்தாளரிடம் கேட்டு மருந்தை பாதுகாப்பாக சேமிக்கவும்."
            ),
            citations=["G-RX-VERIFY", "G-RX-NOCHANGE", "G-PHARMA-ROLE"],
            safety_note=(
                "⚠️ Always verify with your pharmacist. This is not medical advice."
                if lang == "en" else
                "⚠️ மருந்தாளரிடம் சரிபார்க்கவும். இது மருத்துவ ஆலோசனை அல்ல."
            ),
        )

    # ── 3. Blood pressure ─────────────────────────────────────────────────────
    if any(w in text for w in ["blood pressure", "bp", "இரத்த அழுத்தம்", "இரத்த அழுத்த", "hypertension"]):
        return Answer(
            language=lang,
            answer=(
                "High blood pressure often has no symptoms, so it is important to check it regularly. "
                "Reducing salt in your diet, exercising 30 minutes most days, and not smoking are proven ways to help."
                if lang == "en" else
                "உயர் இரத்த அழுத்தத்திற்கு பெரும்பாலும் அறிகுறிகள் இருக்காது. "
                "உணவில் உப்பை குறைத்தல், தினமும் 30 நிமிட உடற்பயிற்சி, புகை பிடிக்காமல் இருப்பது உதவும்."
            ),
            steps=[
                "Check your blood pressure at least once a year.",
                "Reduce salt intake.",
                "Exercise 30 minutes most days.",
                "Take prescribed medicines regularly without skipping.",
            ] if lang == "en" else [
                "ஆண்டுக்கு ஒரு முறையாவது இரத்த அழுத்தம் சரிபார்க்கவும்.",
                "உப்பு குறைத்து சாப்பிடுங்கள்.",
                "தினமும் 30 நிமிட உடற்பயிற்சி செய்யுங்கள்.",
                "மருந்துகளை தவறாமல் எடுங்கள்.",
            ],
            escalation=(
                "See a doctor if your reading is above 140/90 mmHg repeatedly, or if you have headache, blurred vision, or chest pain."
                if lang == "en" else
                "140/90 mmHg-க்கு மேல் திரும்ப திரும்ப வந்தால் மருத்துவரை காணுங்கள்."
            ),
            citations=["G-PREV-BP"],
            safety_note="",
        )

    # ── 4. Diabetes ───────────────────────────────────────────────────────────
    if any(w in text for w in ["diabetes", "sugar", "சர்க்கரை", "நீரிழிவு", "நீரிழிவை", "நீரிழிவ"]):
        return Answer(
            language=lang,
            answer=(
                "Type 2 diabetes risk can be reduced with regular physical activity, "
                "a diet with less refined sugar and more vegetables, and maintaining a healthy weight."
                if lang == "en" else
                "வகை 2 நீரிழிவு அபாயத்தை குறைக்க: சர்க்கரை குறைவாக, காய்கறிகள் அதிகமாக சாப்பிடுங்கள். "
                "தினமும் உடற்பயிற்சி செய்யுங்கள். ஆரோக்கியமான எடை பராமரிக்கவும்."
            ),
            steps=[
                "Get a fasting blood sugar check annually after age 30.",
                "Eat more vegetables and less sugary/processed food.",
                "Exercise regularly.",
                "Take prescribed diabetes medicine exactly as directed.",
            ] if lang == "en" else [
                "30 வயதுக்கு பிறகு ஆண்டுதோறும் பட்டினி இரத்தச் சர்க்கரை சோதிக்கவும்.",
                "காய்கறிகள் அதிகம், சர்க்கரை உணவுகள் குறைவாக சாப்பிடுங்கள்.",
                "தொடர்ந்து உடற்பயிற்சி செய்யுங்கள்.",
                "மருத்துவர் கூறியபடி மருந்து எடுங்கள்.",
            ],
            escalation=(
                "Consult your doctor if you have frequent thirst, increased urination, blurred vision, or slow-healing wounds."
                if lang == "en" else
                "அடிக்கடி தாகம், அதிக சிறுநீர், மங்கலான பார்வை இருந்தால் மருத்துவரை பாருங்கள்."
            ),
            citations=["G-PREV-DIABETES"],
            safety_note="",
        )

    # ── 5. Mental health ──────────────────────────────────────────────────────
    if any(w in text for w in [
        "hopeless", "hopelessness", "don't want to continue", "mental", "stress",
        "anxious", "anxiety", "depressed", "depression", "மன அழுத்தம்",
    ]):
        return Answer(
            language=lang,
            answer=(
                "Mental health matters, and it takes courage to reach out. "
                "You are not alone. Free confidential counselling is available through iCall (9152987821) "
                "and NIMHANS helpline (080-46110007). Talking to a doctor is also a strong first step."
                if lang == "en" else
                "மனநலம் முக்கியம். உதவி கேட்பதில் வெட்கமில்லை. "
                "iCall (9152987821) மற்றும் NIMHANS (080-46110007) இலவச ஆலோசனை வழங்குகின்றன."
            ),
            steps=[
                "Call iCall at 9152987821 for free confidential counselling.",
                "Talk to your doctor about how you are feeling.",
                "You do not have to face this alone.",
            ] if lang == "en" else [
                "இலவச ஆலோசனைக்கு iCall 9152987821 அழைக்கவும்.",
                "உங்கள் உணர்வுகளை மருத்துவரிடம் பகிர்ந்து கொள்ளுங்கள்.",
            ],
            escalation=(
                f"If you or someone is in immediate danger, call {tools.EMERGENCY_NUMBER}. "
                "For mental health support call iCall: 9152987821."
                if lang == "en" else
                f"உடனடி ஆபத்தில் இருந்தால் {tools.EMERGENCY_NUMBER} அழைக்கவும். iCall: 9152987821."
            ),
            citations=["G-MENTAL"],
            safety_note="",
        )

    # ── 6. Default ────────────────────────────────────────────────────────────
    return Answer(
        language=lang,
        answer=(
            "I'm NALAM AI, your health information assistant. I can help with questions about medicines, "
            "preventive health, and finding healthcare facilities in Tamil Nadu. "
            "I cannot diagnose conditions or prescribe medicines—always consult your doctor for that."
            if lang == "en" else
            "நான் NALAM AI, உங்கள் சுகாதார தகவல் உதவியாளர். மருந்துகள், நோய் தடுப்பு மற்றும் "
            "தமிழ்நாட்டில் சுகாதார வசதிகள் பற்றிய கேள்விகளுக்கு உதவுவேன். "
            "நோய் கண்டறிவது அல்லது மருந்து பரிந்துரைப்பது என்னால் முடியாது—அதற்கு மருத்துவரை அணுகுங்கள்."
        ),
        steps=[
            "Ask me about medicines, preventive care, or healthcare facilities.",
            "For emergencies, call 108.",
            "For health advice, call 104.",
        ] if lang == "en" else [
            "மருந்துகள், நோய் தடுப்பு அல்லது சுகாதார வசதிகள் பற்றி கேளுங்கள்.",
            "அவசரநிலைக்கு 108 அழைக்கவும்.",
            "சுகாதார ஆலோசனைக்கு 104 அழைக்கவும்.",
        ],
        escalation=(
            f"For emergencies call {tools.EMERGENCY_NUMBER}. For health advice call {tools.HEALTH_HELPLINE}."
            if lang == "en" else
            f"அவசரநிலைக்கு {tools.EMERGENCY_NUMBER} அழைக்கவும். சுகாதார ஆலோசனைக்கு {tools.HEALTH_HELPLINE} அழைக்கவும்."
        ),
        citations=["G-FACILITY-TN-EMG", "G-FACILITY-NATION"],
        safety_note="",
    )


def build_graph(lang: str, gate: RedFlagGate):
    model = _model()
    planner = Agent(
        model=model,
        name="planner",
        system_prompt=PLANNER.format(lang=lang),
        tools=[tools.lookup_guidance, tools.get_emergency_info, tools.get_healthcare_facilities],
        structured_output_model=Answer,
        callback_handler=None,
    )
    critic = Agent(
        model=model,
        name="critic",
        system_prompt=CRITIC.format(lang=lang, ids=sorted(tools.guidance_ids())),
        structured_output_model=Critique,
        callback_handler=None,
    )

    def should_revise(state):
        r = state.results.get("critic")
        v = getattr(r.result, "structured_output", None) if r else None
        n = sum(1 for x in state.execution_order if x.node_id == "planner")
        if v is not None:
            status = "PASS" if v.ok else "REVISE – " + "; ".join(v.problems)[:200]
            print(f"[critic] pass {n}: {status}", flush=True)
        return bool(v is not None and not v.ok and n < 2)

    b = GraphBuilder()
    b.add_node(planner, "planner")
    b.add_node(critic, "critic")
    b.add_edge("planner", "critic")
    b.add_edge("critic", "planner", condition=should_revise)
    b.set_entry_point("planner")
    b.set_max_node_executions(4)
    b.reset_on_revisit(True)
    b.set_hook_providers([gate])
    return b.build()


def run(case: dict) -> dict:
    """Run the NALAM agent on one case. Returns {plan: Answer.dict, meta: {...}}."""
    t0   = time.time()
    lang = case.get("lang") or tools.language_of(case["text"])
    text = case["text"]
    gate = RedFlagGate(user_text=text, lang=lang)
    meta: dict = {"path": "agent", "passes": 0, "mock": False}

    # ── Emergency gate: code-owned response, no model involved ──────────────
    if tools.is_emergency(text):
        print(f"[safety] EMERGENCY red flag → fixed response, no model", flush=True)
        ans = Answer(
            language=lang,
            answer=tools.emergency_response(lang),
            steps=[f"Call {tools.EMERGENCY_NUMBER} (ambulance) NOW." if lang == "en"
                   else f"இப்போதே {tools.EMERGENCY_NUMBER} (ஆம்புலன்ஸ்) அழைக்கவும்."],
            escalation=tools.emergency_response(lang),
            citations=["G-EMG-CHEST", "G-EMG-BREATHE", "G-EMG-STROKE"],
            safety_note="",
        )
        meta["path"] = "emergency_handoff"
        meta["latency_ms"] = int((time.time() - t0) * 1000)
        return {"plan": ans.model_dump(), "meta": meta}

    # ── Clinical handoff gate ────────────────────────────────────────────────
    if tools.needs_clinical_handoff(text):
        print(f"[safety] CLINICAL red flag → handoff, no model", flush=True)
        ans = Answer(
            language=lang,
            answer=tools.handoff_response(lang),
            steps=(["Ask your doctor or pharmacist directly."] if lang == "en"
                   else ["உங்கள் மருத்துவர் அல்லது மருந்தாளரிடம் நேரடியாக கேளுங்கள்."]),
            escalation=tools.handoff_response(lang),
            citations=["G-RX-NOCHANGE", "G-PHARMA-ROLE"],
            safety_note="",
        )
        meta["path"] = "clinical_handoff"
        meta["latency_ms"] = int((time.time() - t0) * 1000)
        return {"plan": ans.model_dump(), "meta": meta}

    # ── Mock mode: no Bedrock call ───────────────────────────────────────────
    if MOCK:
        print(f"[mock] NALAM_MOCK=1, using mock answer", flush=True)
        ans = _mock_answer(case, lang)
        meta["path"] = "mock"
        meta["mock"] = True
        meta["latency_ms"] = int((time.time() - t0) * 1000)
        return {"plan": ans.model_dump(), "meta": meta}

    # ── Live Bedrock path ────────────────────────────────────────────────────
    try:
        result = build_graph(lang, gate)(
            f"User ({lang}): {text}",
            invocation_state={"user_text": text},
        )
    except RuntimeError:
        if gate.tripped_emergency or gate.tripped_clinical:
            result = None
        else:
            raise

    if gate.tripped_emergency:
        ans = Answer(
            language=lang,
            answer=tools.emergency_response(lang),
            steps=[f"Call {tools.EMERGENCY_NUMBER} NOW."],
            escalation=tools.emergency_response(lang),
            citations=["G-EMG-CHEST"],
            safety_note="",
        )
        meta["path"] = "emergency_handoff"
    elif gate.tripped_clinical:
        ans = Answer(
            language=lang,
            answer=tools.handoff_response(lang),
            steps=["Consult your doctor or pharmacist."],
            escalation=tools.handoff_response(lang),
            citations=["G-RX-NOCHANGE"],
            safety_note="",
        )
        meta["path"] = "clinical_handoff"
    else:
        ans = result.results["planner"].result.structured_output
        if ans is None:
            raise RuntimeError("planner returned no structured answer")
        meta["passes"] = sum(1 for n in result.execution_order if n.node_id == "planner")

    meta["latency_ms"] = int((time.time() - t0) * 1000)
    print(f"[plan] {meta['path']} | {meta['latency_ms']} ms", flush=True)
    return {"plan": ans.model_dump(), "meta": meta}


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m agent.app")
    ap.add_argument("text")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--mock", action="store_true", help="Force mock mode")
    a = ap.parse_args(argv)
    if a.mock:
        os.environ["NALAM_MOCK"] = "1"
    out = run({"text": a.text})
    if a.json:
        print(json.dumps(out, ensure_ascii=False, indent=2))
    else:
        p = out["plan"]
        print(f"\n{'='*60}")
        print(p["answer"])
        if p.get("steps"):
            print("\nNext steps:")
            for s in p["steps"]:
                print(f"  • {s}")
        if p.get("safety_note"):
            print(f"\n{p['safety_note']}")
        print(f"\nEscalation: {p['escalation']}")
        print(f"[{out['meta']['path']} | {out['meta']['latency_ms']} ms]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
