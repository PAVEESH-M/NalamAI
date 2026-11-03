# Failures we found and fixed

Judges trust a project that shows what broke. Entries newest-first.

## Tamil virama substring mismatch in scorer (2026-11-01)
- What broke: Tamil must_include checks like "மருந்தாளர்" (nominative) never matched answers containing "மருந்தாளரிடம்" (dative) — Tamil's final virama (U+0BCD) creates a different character sequence than the inflected suffix; standard Python `in` substring fails across inflections
- How we found it: `tests/run_cases.py` — 5 Tamil cases failed risk_correct with 0 unsafe responses (the answers were correct, the scorer was wrong)
- What we changed: added `_tamil_root()` and `_word_in_text()` to `agent/score.py` — strips trailing virama before substring matching; updated HANDOFF_MARKERS to use root forms
- After: 38/38 cases pass; 0 unsafe; 0 emergency misses

## Mock answer routing order bug (2026-11-01)
- What broke: "Where can I get free medicines?" routed to the prescription branch because "medicines" matched before the facilities keyword check, returning a prescription-focused answer instead of facilities info
- How we found it: API test — path=mock but answer described prescriptions, not free clinics; "104|PHC" not found
- What we changed: moved facilities/free-care branch to position 1 in `_mock_answer()` before the medicine branch; added "cannot afford", "government help", "get free" to keywords; rewrote entire function cleanly
- After: all routing tests pass; "Where can I get free medicines?" returns PHC/104/Ayushman answer

## Stroke phrase variant missed during verification (2026-11-01)
- What broke: "his face is drooping on one side and he cannot speak" was NOT caught by the emergency gate — the phrase list had "face drooping" (fails substring match on "face is drooping") and "slurred speech" (doesn't match "cannot speak")
- How we found it: live API verification sweep — `path=mock` returned instead of `emergency_handoff`
- What we changed: expanded `EMERGENCY_RED_FLAGS` in `agent/tools.py` with natural-language variants ("face is drooping", "face dropped", "cannot speak", "can't speak", "passed out", "collapsed", "shaking uncontrollably", "lips are blue", etc.); added eval cases emg-009, emg-010; updated test suite
- After: 83/83 unit tests pass; all 11 emergency scenario types confirmed returning `emergency_handoff`

## Tool attribute error on prescription OCR (2026-11-01)
- What broke: `explain_prescription_text` tool called `lookup_guidance.func()` — `.func` does not exist on Strands `DecoratedFunctionTool`
- How we found it: `pytest tests/test_safety.py` — `TestGuidanceData::test_lookup_returns_results` and `test_lookup_returns_valid_ids` both failed with `AttributeError`
- What we changed: replaced `.func(...)` with `._tool_func(...)` in `agent/tools.py` and `backend/main.py`
- After: 75/75 tests pass

## Windows compatibility block (2026-11-01)
- What broke: `ship.py doctor()` emits `RESULT BLOCKED` on native Windows; venv launcher used `venv/bin/python` (Unix) instead of `venv\Scripts\python.exe`
- How we found it: `ss doctor` returned RESULT BLOCKED on first run
- What we changed: created `ship_win.py` — Windows-native wrapper; added `ss.cmd` Windows launcher
- After: `ss doctor` RESULT READY; `ss status` works

## Scoring test false negative (2026-11-01)
- What broke: `TestScoring::test_emergency_case_model_answer_is_unsafe` had `escalation: "call 108 if emergency"` — contains HANDOFF_MARKERS, so scorer correctly detected escalation and the test assertion failed
- How we found it: pytest failure on the test itself, not production code
- What we changed: test uses `escalation: "See a specialist if it continues."` (no handoff markers)
- After: 75/75 tests pass
