# -*- coding: utf-8 -*-
"""Build tests/gold/samasa.json -- the samāsa test set for stages C0-C8.

See docs/vidyut-phase-scope.md §10. Kept separate from tests/gold/dataset.json
so the main gold reference number (139/155) never shifts as samāsa cases are
added or re-scoped. Same schema, scored by the same evaluator:

    python scripts/evaluate_gold.py --dataset tests/gold/samasa.json

Every case is self-written (no third-party text, so no licence question).

Scoping convention, reusing the gold set's own meaning of `in_scope`:
  * A *wrong* form targets a rule that is not built yet, so it starts as
    in_scope=False (a known gap) and is flipped to True by the stage that
    ships its rule. `verdict` is that stage's target tier: "error" for a
    rule planned as 🔴-if-clean, "review" for a ⚪-ceiling rule.
  * A *correct* form -- including every form a rule could wrongly flag -- is
    in_scope=True with verdict "correct" from day one. It guards the 🔴 gate:
    it fails the moment any stage asserts an error on correct Sanskrit.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "tests" / "gold" / "samasa.json"

SECTIONS = {
    101: "C2. Correct compounds absent from the lexicon (recognition targets)",
    102: "C1/C2. Meaningless compounds (tracked, not a target)",
    103: "C3. Case ending retained inside a compound (2.4.71)",
    104: "C4. Avyayībhāva endings (2.4.83, 1.2.47, 1.1.41)",
    105: "C5. Tatpuruṣa form rules (6.3.46, 5.4.91)",
    106: "C6. Compound takes gender of last member (2.4.26)",
    107: "C7. Collective dvigu is singular (2.4.1)",
    108: "C8. Dvandva number",
}

cases = []


def add(section, category, inp, correct, verdict, in_scope, surface=None, note="", status=None):
    n = sum(1 for c in cases if c["section"] == section) + 1
    extra = {"expected_status": status} if status else {}
    cases.append({
        "id": f"S{section}-{n:02d}",
        "section": section,
        "section_name": SECTIONS[section],
        "category": category,
        "input": inp,
        "correct": correct,
        "verdict": verdict,
        "in_scope": in_scope,
        "expected_error_surface": surface,
        "expected_split": None,
        "note": note,
        **extra,
    })


def ok(section, category, inp, note=""):
    """A correct sentence that must never draw a 🔴 finding."""
    add(section, category, inp, inp, "correct", True, None, note)


def wrong(section, category, inp, correct, target, surface, note="", shipped=False, status=None):
    """A wrong form; a known gap until its stage ships. Once shipped, `status`
    names the finding the word must carry (see evaluate_gold.py)."""
    add(section, category, inp, correct, target, shipped, surface, note, status)


# ---- 101: correct compounds the lexicon may not carry -----------------------
ok(101, "ṣaṣṭhī-tatpuruṣa", "गुरुभक्तिः वर्धते।", "गुरोः भक्तिः. Measured ⚪ 'not in lexicon' on 2026-09-15.")
ok(101, "ṣaṣṭhī-tatpuruṣa, internal dīrgha sandhi", "देवालयः अस्ति।", "देव + आलय.")
ok(101, "ṣaṣṭhī-tatpuruṣa, internal dīrgha sandhi", "पुस्तकालयः अस्ति।", "पुस्तक + आलय.")
ok(101, "ṣaṣṭhī-tatpuruṣa, internal guṇa sandhi", "सूर्योदयः भवति।", "सूर्य + उदय.")
ok(101, "ṣaṣṭhī-tatpuruṣa", "सत्सङ्गसभा अस्ति।")
ok(101, "karmadhāraya", "नीलकमलम् अस्ति।", "नीलं च तत् कमलम्.")
ok(101, "ṣaṣṭhī-tatpuruṣa", "राजपुत्रः गच्छति।")
ok(101, "karmadhāraya", "विद्याधनम् अस्ति।", "विद्या एव धनम्.")

# ---- 102: meaningless but well-shaped ---------------------------------------
add(102, "three unrelated stems", "गजपुस्तकनदी अस्ति।", "गजपुस्तकनदी अस्ति।", "review", False, None,
    "Grammatically well-shaped, semantically empty. Not a target: C2 is expected "
    "to silence it. Tracked so that cost is visible.")

# ---- 103: C3, case ending retained (सुपो धातुप्रातिपदिकयोः २.४.७१) ----------
wrong(103, "genitive retained", "राज्ञःपुरुषः गच्छति।", "राजपुरुषः गच्छति।", "error", "राज्ञःपुरुषः")
wrong(103, "genitive retained", "नद्याःतीरम् अस्ति।", "नदीतीरम् अस्ति।", "error", "नद्याःतीरम्")
wrong(103, "genitive retained", "देवस्यमन्दिरम् अस्ति।", "देवमन्दिरम् अस्ति।", "error", "देवस्यमन्दिरम्")
ok(103, "aluk: locative retained (6.3.1 ff.)", "सरसिजम् अस्ति।", "सरसि जायते इति.")
ok(103, "aluk: locative retained", "युधिष्ठिरः गच्छति।", "युधि स्थिरः.")
ok(103, "aluk: locative retained", "वनेचरः गच्छति।")
ok(103, "aluk: locative retained", "खेचरः गच्छति।")
ok(103, "aluk: dative retained", "परस्मैपदम् अस्ति।")
ok(103, "aluk: dative retained", "आत्मनेपदम् अस्ति।")
ok(103, "two words joined by vowel sandhi, not a compound", "देवस्यालयः अस्ति।",
   "देवस्य + आलयः by सवर्णदीर्घ. Same letters a case-retention rule would see; must not fire.")
ok(103, "two words joined by vowel sandhi, not a compound", "रामस्याश्रमः अस्ति।")

# ---- 104: C4, avyayībhāva ---------------------------------------------------
wrong(104, "4a: a-stem must end in -am (2.4.83)", "बालः उपकृष्णः तिष्ठति।", "बालः उपकृष्णं तिष्ठति।",
      "review", "उपकृष्णः",
      "Out of reach by design: the Kosha carries उपकृष्ण as a word, and C4 never overrides a "
      "lexicon hit (that gate is what keeps it off correct prādi compounds).")
wrong(104, "4b: final long vowel shortened (1.2.47)", "ग्रामः उपगङ्गाम् अस्ति।", "ग्रामः उपगङ्गम् अस्ति।",
      "review", "उपगङ्गाम्",
      "Planned as the best 🔴 candidate; shipped ⚪. DCS offers no evidence either way "
      "(0 candidate words), so 'fires on no DCS sentence' was vacuous here.",
      shipped=True, status="samasa_error")
wrong(104, "4c: indeclinable takes no case ending (2.4.82)", "सः यथाशक्तिः पठति।", "सः यथाशक्ति पठति।",
      "review", "यथाशक्तिः", shipped=True, status="samasa_error")
wrong(104, "4c: indeclinable takes no case ending (2.4.83)", "सः प्रतिदिनेषु पठति।", "सः प्रतिदिनं पठति।",
      "review", "प्रतिदिनेषु", shipped=True, status="samasa_error")
wrong(104, "4c: indeclinable takes no case ending (2.4.82)", "सः यथाविधिः करोति।", "सः यथाविधि करोति।",
      "review", "यथाविधिः", shipped=True, status="samasa_error")
wrong(104, "4b+4c: long vowel, and no case ending (1.2.47)", "ग्रामः उपनद्याम् अस्ति।", "ग्रामः उपनदि अस्ति।",
      "review", "उपनद्याम्", shipped=True, status="samasa_error")
wrong(104, "4a: declined ending; was a wrong 🔴 spelling correction", "सः प्रतिमासाः आगच्छति।",
      "सः प्रतिमासम् आगच्छति।", "review", "प्रतिमासाः",
      "Until the samāsa check ran ahead of the spelling corrector, this drew a 🔴 'correction' to "
      "the unrelated प्रतिमांसाः.", shipped=True, status="samasa_error")
wrong(104, "4b: long vowel; was a 🔴 spelling correction", "ग्रामः अनुगङ्गाम् अस्ति।", "ग्रामः अनुगङ्गम् अस्ति।",
      "review", "अनुगङ्गाम्",
      "Reached the right spelling before, but asserted 🔴 under a spelling-error label.",
      shipped=True, status="samasa_error")
ok(104, "correct avyayībhāva, -am", "ग्रामः उपगङ्गम् अस्ति।")
ok(104, "correct avyayībhāva, -am, anusvāra", "सः प्रतिदिनं पठति।")
ok(104, "correct avyayībhāva, no ending", "सः यथाशक्ति पठति।",
   "Drew ⚪ 'not in lexicon' before C4 added a यथा- recognition path.")
ok(104, "correct avyayībhāva, no ending", "सः यथाविधि करोति।")
ok(104, "correct avyayībhāva, shortened -i", "ग्रामः उपनदि अस्ति।")
ok(104, "optional locative (2.4.84)", "घटः उपकुम्भे अस्ति।")
ok(104, "prādi noun, declined correctly", "उपवनानि सन्ति।", "The raw rule would propose उपवनम्; the lexicon gate stops it.")
ok(104, "prādi noun, declined correctly", "उपकरणानि सन्ति।")
ok(104, "prādi noun, declined correctly", "सा प्रतिज्ञाम् करोति।", "The raw rule would propose प्रतिज्ञम्.")
ok(104, "उप-initial, not avyayībhāva", "उपाध्यायः पाठयति।")
ok(104, "अनु-initial, not avyayībhāva", "अनुजः गच्छति।")
ok(104, "प्रति-initial, not avyayībhāva", "प्रतिनिधिः आगच्छति।")
ok(104, "उप-initial, not avyayībhāva", "उपग्रहः अस्ति।")
ok(104, "optional -āt in the ablative (2.4.83)", "जलम् उपकुम्भात् आनय।")


# ---- 105: C5, tatpuruṣa form rules ------------------------------------------
_C5A_NOTE = ("Planned 🔴-if-clean; shipped ⚪: a षष्ठी-तत्पुरुष keeps महत्- (महत्सेवा), and form "
             "alone cannot tell the two apart.")
wrong(105, "5a: mahat -> mahā (6.3.46)", "महत्पुरुषः आगच्छति।", "महापुरुषः आगच्छति।", "review", "महत्पुरुषः",
      _C5A_NOTE, shipped=True, status="samasa_error")
wrong(105, "5a: mahat -> mahā", "महत्देवः पूज्यते।", "महादेवः पूज्यते।", "review", "महत्देवः",
      _C5A_NOTE, shipped=True, status="samasa_error")
wrong(105, "5a: mahat -> mahā, jaśtva spelling", "महद्देवः पूज्यते।", "महादेवः पूज्यते।", "review", "महद्देवः",
      _C5A_NOTE, shipped=True, status="samasa_error")
wrong(105, "5a: mahat -> mahā, then guṇa", "महदीश्वरः पूज्यते।", "महेश्वरः पूज्यते।", "review", "महदीश्वरः",
      _C5A_NOTE, shipped=True, status="samasa_error")
wrong(105, "5b: ṭac samāsānta (5.4.91)", "महाराजा आगच्छति।", "महाराजः आगच्छति।", "error", "महाराजा",
      "5b not built. महाराजा is in the lexicon because it is the correct बहुव्रीहि spelling "
      "(ṭac is tatpuruṣa-only); so are देवराजा, धर्मराजा, कृष्णसखा. The rule could only fire by "
      "overriding a lexicon hit.")
ok(105, "not samānādhikaraṇa: 6.3.46 does not apply", "महत्सेवा कर्तव्या।", "महतां सेवा.")
ok(105, "taddhita, not a compound", "महत्त्वम् अस्ति।")
ok(105, "'Mahat and the rest': not samānādhikaraṇa", "महदादि लिङ्गम्।",
   "DCS (Experiment 2 source text). Drew a 🔴 'correction' to महदाद्, then briefly a ⚪ महादि.")
ok(105, "comparative, not a compound", "महत्तरः अस्ति।")
ok(105, "mahā correctly applied", "महात्मा गच्छति।")
ok(105, "mahā correctly applied, with guṇa", "महेश्वरः पूज्यते।")
ok(105, "न पूजनात् (5.4.69) blocks ṭac", "सुराजा शास्ति।")

# C6-C8 were prototyped and measured on 2026-09-17 and not built; the wrong
# forms stay here as permanent known gaps. See docs/vidyut-phase-scope.md §10.11.
_C6_NOTE = ("Not built: a masculine compound whose last member has a feminine homograph "
            "stem looks identical (षोडशगुणः, सुखदुःखयोगः); the prototype fired on 41 correct DCS words.")
_C7_NOTE = ("Not built: त्रिभुवनानि, पञ्चपात्राणि and त्रिलोकाः are lexicon hits, and a numeral-first "
            "plural is also a correct बहुव्रीहि (पञ्चमुखाः).")
_C8_NOTE = ("Not built: any singular two-stem तत्पुरुष looks like a mis-numbered द्वन्द्व; the prototype "
            "fired on 7 correct DCS words (सङ्गदोषः, नियोगपर्यायः) and on no real error.")

# ---- 106: C6, last-member gender (परवल्लिङ्गं द्वन्द्वतत्पुरुषयोः २.४.२६) -----
wrong(106, "tatpuruṣa with feminine last member", "राजकन्यः गच्छति।", "राजकन्या गच्छति।", "review", "राजकन्यः",
      _C6_NOTE)
wrong(106, "tatpuruṣa with feminine last member", "देवसेनः युध्यते।", "देवसेना युध्यते।", "review", "देवसेनः",
      "⚪ ceiling: देवसेन is also a possible bahuvrīhi/name.")
ok(106, "bahuvrīhi takes referent's gender", "पीताम्बरा बाला अस्ति।", "Was a ⚪ false positive until 2026-09-15.")
ok(106, "bahuvrīhi, feminine in -ī", "चन्द्रमुखी बाला अस्ति।")

# ---- 107: C7, collective dvigu singular (द्विगुरेकवचनम् २.४.१) ---------------
wrong(107, "samāhāra dvigu written plural", "सः त्रिभुवनानि जयति।", "सः त्रिभुवनं जयति।", "review", "त्रिभुवनानि",
      _C7_NOTE)
ok(107, "numeral-initial bahuvrīhi", "पञ्चाननः गर्जति।")
ok(107, "numeral-initial bahuvrīhi", "त्रिनेत्रः शिवः अस्ति।")
ok(107, "saṃjñā dvigu, correctly plural (2.1.50)", "सप्तर्षयः सन्ति।")

# ---- 108: C8, dvandva number ------------------------------------------------
wrong(108, "itaretara, two members: dual", "रामलक्ष्मणः वनं गच्छतः।", "रामलक्ष्मणौ वनं गच्छतः।", "review", "रामलक्ष्मणः",
      _C8_NOTE)
wrong(108, "itaretara, three members: plural", "रामलक्ष्मणभरतौ गच्छन्ति।", "रामलक्ष्मणभरताः गच्छन्ति।", "review", "रामलक्ष्मणभरतौ",
      _C8_NOTE)
ok(108, "itaretara dual", "रामलक्ष्मणौ वनं गच्छतः।")
ok(108, "samāhāra, neuter singular", "पाणिपादम् प्रक्षालयति।")
ok(108, "itaretara dual with ānaṅ", "मातापितरौ नमामि।")
ok(108, "ṣaṣṭhī-tatpuruṣa of two names", "रामदूतः गच्छति।")

OUT.write_text(json.dumps({
    "_comment": "Samāsa test set for stages C0-C8. Built by scripts/build_samasa_dataset.py; "
                "see docs/vidyut-phase-scope.md §10.",
    "cases": cases,
}, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"wrote {len(cases)} cases to {OUT.relative_to(ROOT)}")
