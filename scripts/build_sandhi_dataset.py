# -*- coding: utf-8 -*-
"""Build tests/gold/sandhi.json -- regression cases for the sandhi advisories
added in docs/vidyut-phase-scope.md §10.9 and §10.13.

Separate from tests/gold/dataset.json for the same reason as samasa.json: the
main gold reference number (139/155) must not move. Scored by the same
evaluator:

    python scripts/evaluate_gold.py --dataset tests/gold/sandhi.json

Everything here is ⚪ by design -- an unjoined junction is a legitimate
editorial convention, never an asserted error -- so a wrong form is recorded
with verdict "review" plus `expected_status`, which requires that exact word to
carry the finding (silence does not pass), and a correct form with verdict
"correct", which fails if anything is ever asserted on it.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "gold" / "sandhi.json"

SECTIONS = {
    201: "सः/एषः lose the ending before a consonant (6.1.132)",
    202: "Pada-final -र् (पुनर्, प्रातर्, अन्तर्)",
    203: "Anusvāra written before a vowel (8.3.23)",
}
cases = []


def add(section, category, inp, correct, verdict, surface=None, status=None, note=""):
    n = sum(1 for c in cases if c["section"] == section) + 1
    extra = {"expected_status": status} if status else {}
    cases.append({
        "id": f"D{section}-{n:02d}", "section": section, "section_name": SECTIONS[section],
        "category": category, "input": inp, "correct": correct, "verdict": verdict,
        "in_scope": True, "expected_error_surface": surface, "expected_split": None,
        "note": note, **extra,
    })


def flags(section, category, inp, correct, surface, note=""):
    add(section, category, inp, correct, "review", surface, "sandhi_error", note)


def ok(section, category, inp, note=""):
    add(section, category, inp, inp, "correct", None, None, note)


# ---- 201: एतत्तदोः सुलोपोऽकोरनञ्समासे हलि (६.१.१३२) --------------------------
flags(201, "सः before a voiced consonant", "सः गच्छति।", "स गच्छति।", "सः",
      "Suggested सो (हशि च) until 2026-09-17.")
flags(201, "एषः before a voiced consonant", "एषः गच्छति।", "एष गच्छति।", "एषः")
flags(201, "the wrong -ओ form as written", "सो गच्छति।", "स गच्छति।", "सो",
      "Silently accepted until 2026-09-17.")
ok(201, "correct सुलोप", "स गच्छति।")
ok(201, "before a voiceless consonant: ordinary modern spelling, not flagged", "सः पठति।",
   "Gold 11-114 marks this must-not-flag.")
ok(201, "before अ: ६.१.११३ applies, not ६.१.१३२", "सोऽपि गच्छति।")
ok(201, "यद्/किम् are not in the sūtra", "यः गच्छति।")

# ---- 202: pada-final -र् ------------------------------------------------------
flags(202, "-र् stays before a voiced consonant", "पुनः गुरोः गृहम्।", "पुनर्गुरोः गृहम्।", "पुनः",
      "Suggested पुनो until 2026-09-17.")
flags(202, "-र् stays before a vowel", "पुनः अपि।", "पुनरपि।", "पुनः")
flags(202, "-र् before -र्: lopa and lengthening (८.३.१४ / ६.३.१११)", "प्रातः रामः उत्तिष्ठति।",
      "प्राता रामः उत्तिष्ठति।", "प्रातः", "Suggested प्रातो until 2026-09-17.")
flags(202, "अन्तर् before a voiced consonant", "अन्तः गच्छति।", "अन्तर्गच्छति।", "अन्तः")
flags(202, "श्चुत्व before च (८.३.३४ / ८.४.४०)", "पुनः च।", "पुनश्च।", "पुनः")
ok(202, "visarga is correct before a voiceless consonant", "पुनः पठति।")
ok(202, "ordinary -स् word keeps हशि च", "रामः गच्छति।",
   "Its suggestion must stay रामो, not रामर्.")

# ---- 203: मोऽनुस्वारः (८.३.२३) ------------------------------------------------
flags(203, "anusvāra before a vowel", "शीघ्रं उत्तिष्ठति।", "शीघ्रम् उत्तिष्ठति।", "शीघ्रं",
      "From the real-text sample; not flagged at all until 2026-09-17.")
flags(203, "anusvāra before a vowel", "सौन्दर्यं अपश्यताम्।", "सौन्दर्यम् अपश्यताम्।", "सौन्दर्यं")
flags(203, "anusvāra before a vowel, infinitive", "गन्तुं इच्छति।", "गन्तुम् इच्छति।", "गन्तुं")
ok(203, "anusvāra before a consonant is correct", "जलं पिबन्ति।")
ok(203, "म् written before a vowel", "शीघ्रम् उत्तिष्ठति।")
ok(203, "anusvāra before a consonant is correct", "फलं खादति।")

OUT.write_text(json.dumps({
    "_comment": "Sandhi advisory regressions. Built by scripts/build_sandhi_dataset.py; "
                "see docs/vidyut-phase-scope.md §10.9 and §10.13.",
    "cases": cases,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {len(cases)} cases to {OUT.relative_to(ROOT)}")
