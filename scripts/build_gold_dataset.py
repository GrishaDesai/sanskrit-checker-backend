# -*- coding: utf-8 -*-
"""
Builds tests/gold/dataset.json from the 150-case gold test matrix.

Each case has:
  id             stable id, "<section>-<n>"
  section        section number (1-14) matching the source matrix
  section_name   human label for the section
  category       specific error-type / phenomenon label
  input          Devanagari text given to the checker
  correct        the corrected/reference Devanagari form (None if not applicable)
  verdict        expected checker verdict:
                   "error"   - must be flagged as a confirmed problem
                   "review"  - must NOT be flagged as a hard error, but may be
                               surfaced as a style/consistency/review note
                   "correct" - must not be flagged at all (false-positive test)
  in_scope       whether the *current* engine design is expected to be able to
                   decide this at all (False = known/declared gap, not a bug)
  expected_error_surface  the specific token expected to carry the flag, if any
  expected_split          for sandhi-splitting cases: the expected pada sequence
  note           rationale / gloss, incl. why verdict != naive reading of table

Run:  python scripts/build_gold_dataset.py
"""
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "tests" / "gold" / "dataset.json"

cases = []


def add(id_, section, section_name, category, input_, correct=None, verdict="error",
        in_scope=True, error_surface=None, expected_split=None, note=""):
    cases.append({
        "id": id_,
        "section": section,
        "section_name": section_name,
        "category": category,
        "input": input_,
        "correct": correct,
        "verdict": verdict,
        "in_scope": in_scope,
        "expected_error_surface": error_surface,
        "expected_split": expected_split,
        "note": note,
    })


S1 = "1. Spelling / Orthographic Errors"
add("1-01", 1, S1, "Missing Visarga", "राम गच्छति।", "रामः गच्छति।", "error", True, "राम")
add("1-02", 1, S1, "Missing Visarga", "बालक गच्छति।", "बालकः गच्छति।", "error", True, "बालक")
add("1-03", 1, S1, "Missing anusvara / case ending", "गुरुः शिष्य शिक्षयति।", "गुरुः शिष्यं शिक्षयति।", "error", True, "शिष्य")
add("1-04", 1, S1, "Spelling", "विधालयः", "विद्यालयः", "error", True, "विधालयः")
add("1-05", 1, S1, "Incorrect word segmentation", "विद्या लयः", "विद्यालयः", "error", False,
    note="Both विद्या and लयः are independently valid words; catching this requires "
         "detecting that two valid adjacent words are more likely a wrongly-split "
         "single word/compound. No current layer attempts this (out of scope).")
add("1-06", 1, S1, "Spelling", "संस्क्रुतम्", "संस्कृतम्", "error", True, "संस्क्रुतम्")
add("1-07", 1, S1, "Consonant error", "सन्स्कृतम्", "संस्कृतम्", "error", True, "सन्स्कृतम्")
add("1-08", 1, S1, "Missing consonant", "प्रथना", "प्रार्थना", "error", True, "प्रथना")
add("1-09", 1, S1, "Spelling / anusvara", "स्वास्थ्यम्", "स्वास्थ्यं", "review", False,
    note="स्वास्थ्यम् (final म्) is itself a valid word in isolation; म् vs ं is a "
         "sandhi/style choice that depends on the following word, not decidable "
         "from this token alone.")
add("1-10", 1, S1, "Spelling", "आर्शीवादः", "आशीर्वादः", "error", True, "आर्शीवादः")
add("1-11", 1, S1, "Vowel placement", "आशिर्वादः", "आशीर्वादः", "error", True, "आशिर्वादः")
add("1-12", 1, S1, "Vowel error", "क्रिपया", "कृपया", "error", True, "क्रिपया")
add("1-13", 1, S1, "Incorrect vowel", "कॄपया", "कृपया", "error", True, "कॄपया")
add("1-14", 1, S1, "Conjunct error", "श्रध्दा", "श्रद्धा", "error", True, "श्रध्दा")
add("1-15", 1, S1, "Conjunct error", "बुध्दिः", "बुद्धिः", "error", True, "बुध्दिः")
add("1-16", 1, S1, "Conjunct error", "सिध्दिः", "सिद्धिः", "error", True, "सिध्दिः")
add("1-17", 1, S1, "Missing consonant", "उद्देशः", "उद्देश्यः", "review", False,
    note="उद्देशः is itself a distinct valid word (place/spot), not a malformed "
         "spelling of उद्देश्यः; flagging it as an error requires semantic/context "
         "judgement, not orthography.")
add("1-18", 1, S1, "Missing consonant", "अध्यनम्", "अध्ययनम्", "error", True, "अध्यनम्")
add("1-19", 1, S1, "Orthographic variant — review", "स्वतन्त्र", "स्वतंत्र", "review", True, "स्वतन्त्र",
    note="न् vs ं before त् is a permitted orthographic variant, not an error.")
add("1-20", 1, S1, "Spelling", "परिक्षा", "परीक्षा", "error", True, "परिक्षा")

S2 = "2. Case / विभक्ति Errors"
add("2-21", 2, S2, "Correct baseline", "रामः वनं गच्छति।", None, "correct")
add("2-22", 2, S2, "Incorrect case", "रामः वनः गच्छति।", "रामः वनं गच्छति।", "error", True, "वनः")
add("2-23", 2, S2, "Accusative error", "रामः गुरुः नमति।", "रामः गुरुम् नमति।", "error", True, "गुरुः")
add("2-24", 2, S2, "Correct baseline", "रामः गुरुम् नमति।", None, "correct")
add("2-25", 2, S2, "Correct baseline", "रामस्य पिता आगच्छति।", None, "correct")
add("2-26", 2, S2, "Genitive error", "रामः पिता आगच्छति।", "रामस्य पिता आगच्छति।", "error", True, "रामः")
add("2-27", 2, S2, "Instrumental error", "सीता रामेन सह गच्छति।", "सीता रामेण सह गच्छति।", "error", True, "रामेन")
add("2-28", 2, S2, "Subject/case error", "रामेन विद्यालयं गच्छति।", "रामः विद्यालयं गच्छति।", "error", True, "रामेन")
add("2-29", 2, S2, "Correct baseline", "गुरुः शिष्याय ज्ञानं ददाति।", None, "correct")
add("2-30", 2, S2, "Dative error", "गुरुः शिष्यं ज्ञानं ददाति।", "गुरुः शिष्याय ज्ञानं ददाति।", "error", True, "शिष्यं")
add("2-31", 2, S2, "Correct baseline", "बालकः कक्षायां पठति।", None, "correct")
add("2-32", 2, S2, "Locative error", "बालकः कक्षां पठति।", "बालकः कक्षायां पठति।", "error", True, "कक्षां")

S3 = "3. Number / वचन Errors"
add("3-33", 3, S3, "Singular verb mismatch", "बालकः पठन्ति।", "बालकः पठति।", "error", True, "पठन्ति")
add("3-34", 3, S3, "Plural verb mismatch", "बालकाः पठति।", "बालकाः पठन्ति।", "error", True, "पठति")
add("3-35", 3, S3, "Dual verb mismatch", "बालकौ पठति।", "बालकौ पठतः।", "error", True, "पठति")
add("3-36", 3, S3, "Plural verb mismatch", "ते गच्छति।", "ते गच्छन्ति।", "error", True, "गच्छति")
add("3-37", 3, S3, "Singular/plural mismatch", "सः गच्छन्ति।", "सः गच्छति।", "error", True, "गच्छन्ति")
add("3-38", 3, S3, "Dual mismatch", "तौ गच्छन्ति।", "तौ गच्छतः।", "error", True, "गच्छन्ति")
add("3-39", 3, S3, "Person/number mismatch", "वयं गच्छति।", "वयं गच्छामः।", "error", True, "गच्छति")
add("3-40", 3, S3, "Person mismatch", "अहं गच्छसि।", "अहं गच्छामि।", "error", True, "गच्छसि")

S4 = "4. पुरुष / Person Errors"
add("4-41", 4, S4, "Person", "अहं पठसि।", "अहं पठामि।", "error", True, "पठसि")
add("4-42", 4, S4, "Person", "त्वं पठामि।", "त्वं पठसि।", "error", True, "पठामि")
add("4-43", 4, S4, "Person", "सः पठामि।", "सः पठति।", "error", True, "पठामि")
add("4-44", 4, S4, "Person", "वयं पठथ।", "वयं पठामः।", "error", True, "पठथ")
add("4-45", 4, S4, "Person", "यूयं पठामः।", "यूयं पठथ।", "error", True, "पठामः")
add("4-46", 4, S4, "Person", "ते पठथ।", "ते पठन्ति।", "error", True, "पठथ")

S5 = "5. Gender / लिङ्ग Errors"
add("5-47", 5, S5, "Gender agreement", "सुन्दरः बालिका।", "सुन्दरी बालिका।", "error", True, "सुन्दरः")
add("5-48", 5, S5, "Gender agreement", "सुन्दरी बालकः।", "सुन्दरः बालकः।", "error", True, "सुन्दरी")
add("5-49", 5, S5, "Pronoun gender", "सः बालिका अस्ति।", "सा बालिका अस्ति।", "error", True, "सः")
add("5-50", 5, S5, "Pronoun gender", "सा बालकः अस्ति।", "सः बालकः अस्ति।", "error", True, "सा")
add("5-51", 5, S5, "Gender agreement", "एषः नदी।", "एषा नदी।", "error", True, "एषः")
add("5-52", 5, S5, "Gender agreement", "एषा वृक्षः।", "एषः वृक्षः।", "error", True, "एषा")

S6 = "6. Verb / धातु / लकार Errors"
add("6-53", 6, S6, "Verb/person", "रामः पठसि।", "रामः पठति।", "error", True, "पठसि")
add("6-54", 6, S6, "Verb/number", "रामः गच्छन्ति।", "रामः गच्छति।", "error", True, "गच्छन्ति")
add("6-55", 6, S6, "Correct baseline", "रामः अगच्छत्।", None, "correct")
add("6-56", 6, S6, "Tense/context issue", "रामः अगच्छति।", "रामः गच्छति।", "review", False, "अगच्छति",
    note="अगच्छति mixes the लङ् augment अ- with a Latin-style present ending; it is "
         "not a real tiṅanta of any lakāra, so this is really a malformed-form "
         "case, not a live tense/context ambiguity. Kept as review pending a "
         "generalized tiṅanta-repair layer, not because it's ambiguous.")
add("6-57", 6, S6, "Orthography", "बालकः पुस्तकम् पठति।", "बालकः पुस्तकं पठति।", "review", False, "पुस्तकम्",
    note="पुस्तकम् vs पुस्तकं before a following प is a sandhi/anusvāra writing "
         "convention (म् + labial), not an independent spelling error.")
add("6-58", 6, S6, "Verb agreement", "बालकः पुस्तकं पठन्ति।", "बालकः पुस्तकं पठति।", "error", True, "पठन्ति")
add("6-59", 6, S6, "Verb agreement", "बालकाः पुस्तकं पठति।", "बालकाः पुस्तकं पठन्ति।", "error", True, "पठति")
add("6-60", 6, S6, "Verb agreement", "ते विद्यालयं गच्छति।", "ते विद्यालयं गच्छन्ति।", "error", True, "गच्छति")

S7 = "7. Sandhi Errors"
SANDHI_NOTE = ("Per the spec's own caveat: an unsandhied form (रामः गच्छति) is not "
               "itself invalid Sanskrit even where रामो गच्छति is the sandhi-joined "
               "form. Modeled as 'review' (style-tier, offered not asserted), never "
               "hard 'error' — matching the documented design that unapplied "
               "external sandhi is a legitimate editorial convention.")
add("7-61", 7, S7, "Visarga Sandhi", "रामः गच्छति।", "रामो गच्छति।", "review", True, note=SANDHI_NOTE)
add("7-62", 7, S7, "Visarga + vowel", "रामः अस्ति।", "रामोऽस्ति।", "review", True, note=SANDHI_NOTE)
add("7-63", 7, S7, "Sandhi/context — review", "नरः इह अस्ति।", "नरोऽत्र अस्ति।", "review", False,
    note="Reference correction also swaps इह->अत्र (word choice), not just sandhi; "
         "judging word choice is out of scope for a grammar/sandhi checker.")
add("7-64", 7, S7, "Visarga Sandhi", "सः अपि गच्छति।", "सोऽपि गच्छति।", "review", True, note=SANDHI_NOTE)
add("7-65", 7, S7, "Sandhi", "रामः एव गच्छति।", "राम एव गच्छति।", "review", True, note=SANDHI_NOTE)
add("7-66", 7, S7, "Consonant/vowel sandhi", "तत् एव।", "तदेव।", "review", True,
    note="Near-obligatory cliticization in running prose; still modeled as review "
         "rather than hard error, consistent with this section's general policy.")
add("7-67", 7, S7, "Sandhi", "तत् अपि।", "तदपि।", "review", True)
add("7-68", 7, S7, "Sandhi", "तत् अर्थम्।", "तदर्थम्।", "review", True)
add("7-69", 7, S7, "Vowel Sandhi", "विद्या आलयः।", "विद्यालयः।", "review", True)
add("7-70", 7, S7, "Vowel Sandhi", "महा उत्सवः।", "महोत्सवः।", "review", True)
add("7-71", 7, S7, "Vowel Sandhi", "देव इन्द्रः।", "देवेन्द्रः।", "review", True)
add("7-72", 7, S7, "Vowel Sandhi", "नर इन्द्रः।", "नरेन्द्रः।", "review", True)
add("7-73", 7, S7, "Vowel Sandhi", "सुर ईशः।", "सुरेशः।", "review", True)
add("7-74", 7, S7, "Vowel Sandhi", "गण ईशः।", "गणेशः।", "review", True)

S8 = "8. Sandhi Splitting Tests"
add("8-75", 8, S8, "Sandhi splitting", "रामो गच्छति।", None, "correct", True, expected_split=["रामः", "गच्छति"])
add("8-76", 8, S8, "Sandhi splitting", "रामोऽस्ति।", None, "correct", True, expected_split=["रामः", "अस्ति"])
add("8-77", 8, S8, "Sandhi splitting", "सोऽपि गच्छति।", None, "correct", True, expected_split=["सः", "अपि", "गच्छति"])
add("8-78", 8, S8, "Sandhi splitting", "तदेव।", None, "correct", True, expected_split=["तत्", "एव"])
add("8-79", 8, S8, "Sandhi splitting", "तदपि।", None, "correct", True, expected_split=["तत्", "अपि"])
add("8-80", 8, S8, "Sandhi splitting", "तदर्थम्।", None, "correct", True, expected_split=["तत्", "अर्थम्"])
add("8-81", 8, S8, "Sandhi splitting", "महोत्सवः।", None, "correct", True, expected_split=["महा", "उत्सवः"])
add("8-82", 8, S8, "Sandhi splitting", "देवेन्द्रः।", None, "correct", True, expected_split=["देव", "इन्द्रः"])
add("8-83", 8, S8, "Sandhi splitting", "नरेन्द्रः।", None, "correct", True, expected_split=["नर", "इन्द्रः"])
add("8-84", 8, S8, "Sandhi splitting", "सुरेशः।", None, "correct", True, expected_split=["सुर", "ईशः"])

S9 = "9. Compound / समास Tests"
add("9-85", 9, S9, "Compound", "राजपुरुषः", "राज्ञः पुरुषः", "review", True)
add("9-86", 9, S9, "Compound", "नीलकमलम्", "नीलं कमलम्", "review", True)
add("9-87", 9, S9, "Compound", "महापुरुषः", "महान् पुरुषः", "review", True)
add("9-88", 9, S9, "Compound", "देवालयः", "देवस्य आलयः", "review", True)
add("9-89", 9, S9, "Compound", "ग्रामवासी", "ग्रामे वसति इति", "review", False,
    note="Not in the supplemental/known-compound tables; requires generic "
         "structural decomposition, not a fixed lookup.")
add("9-90", 9, S9, "Compound", "जलपानम्", "जलस्य पानम्", "review", False)
add("9-91", 9, S9, "Compound", "राजमार्गः", "राज्ञः मार्गः", "review", False)
add("9-92", 9, S9, "Compound", "धर्मशास्त्रम्", "धर्मस्य शास्त्रम्", "review", False)
add("9-93", 9, S9, "Compound / Dvandva", "मातापितरौ", "माता च पिता च", "review", False)
add("9-94", 9, S9, "Compound", "नीलोत्पलम्", "नीलम् उत्पलम्", "review", False)

S10 = "10. Unknown Word / Proper Noun Tests"
add("10-95", 10, S10, "Proper noun", "रामः विद्यालयं गच्छति।", None, "correct")
add("10-96", 10, S10, "Proper noun", "कृष्णः गच्छति।", None, "correct")
add("10-97", 10, S10, "Place name", "वाराणसी नगरी अस्ति।", None, "review")
add("10-98", 10, S10, "Place name", "अयोध्या नगरी प्रसिद्धा अस्ति।", None, "review")
add("10-99", 10, S10, "Proper noun", "हिमालयः विशालः अस्ति।", None, "correct")
add("10-100", 10, S10, "Unknown/technical", "अमुकशब्दः अत्र प्रयुक्तः।", None, "review")
add("10-101", 10, S10, "Possible technical term", "विशेषसंज्ञा", None, "review")
add("10-102", 10, S10, "Possible compound", "पुस्तकनाम", None, "review")

S11 = "11. Correct Sanskrit — MUST NOT FLAG"
_s11 = [
    "रामः वनं गच्छति।", "रामो गच्छति।", "सीता विद्यालयं गच्छति।", "बालकः पुस्तकं पठति।",
    "बालकाः पुस्तकं पठन्ति।", "गुरुः शिष्यं शिक्षयति।", "गुरुः शिष्याय ज्ञानं ददाति।",
    "रामस्य पिता आगच्छति।", "सीता रामेण सह गच्छति।", "अहं संस्कृतं पठामि।",
    "त्वं संस्कृतं पठसि।", "सः संस्कृतं पठति।", "वयं संस्कृतं पठामः।", "यूयं संस्कृतं पठथ।",
    "ते संस्कृतं पठन्ति।", "तदेव सत्यम्।", "तदपि आवश्यकम्।", "रामोऽपि गच्छति।",
]
for _i, _s in enumerate(_s11, start=103):
    add(f"11-{_i}", 11, S11, "must_not_flag", _s, None, "correct")

S12 = "12. Unicode / Devanagari Tests"
add("12-121", 12, S12, "Valid Unicode", "रामः", None, "correct")
add("12-122", 12, S12, "Valid", "रामः।", None, "correct")
add("12-123", 12, S12, "Extra whitespace", "रामः  गच्छति।", None, "review", True,
    note="Double space between words: formatting note, not a grammar error.")
add("12-124", 12, S12, "Missing whitespace", "रामःगच्छति।", None, "review", True,
    note="Fused tokens with no space; should not be silently mis-tokenized or "
         "flagged as an unknown word without comment.")
add("12-125", 12, S12, "Punctuation review", "रामः, गच्छति।", None, "review", True,
    note="Comma is not standard Sanskrit punctuation (danda-based); flagged as a "
         "typography note, not a grammar error.")
add("12-126", 12, S12, "Whitespace before punctuation", "रामः ।", None, "review", True)
add("12-127", 12, S12, "Missing space after punctuation", "रामः।गच्छति।", None, "review", True)
add("12-128", 12, S12, "Newline handling", "रामः\nगच्छति।", None, "correct", True,
    note="A newline is a legitimate sentence/line break; must not itself be treated as an error.")
add("12-129", 12, S12, "Tab handling", "रामः\tगच्छति।", None, "review", True)
add("12-130", 12, S12, "Duplicate whitespace", "रामः   गच्छति।", None, "review", True)

S13 = "13. OCR Error Tests"
add("13-131", 13, S13, "OCR/consonant duplication", "रामः गछ्छति।", "रामः गच्छति।", "error", True, "गछ्छति")
add("13-132", 13, S13, "OCR/spelling", "विधालयः", "विद्यालयः", "error", True, "विधालयः")
add("13-133", 13, S13, "OCR", "सन्स्कृतम्", "संस्कृतम्", "error", True, "सन्स्कृतम्")
add("13-134", 13, S13, "OCR/conjunct", "बुध्दिः", "बुद्धिः", "error", True, "बुध्दिः")
add("13-135", 13, S13, "OCR", "श्रध्दा", "श्रद्धा", "error", True, "श्रध्दा")
add("13-136", 13, S13, "OCR", "अधययनम्", "अध्ययनम्", "error", True, "अधययनम्")
add("13-137", 13, S13, "OCR/spelling", "परिक्षा", "परीक्षा", "error", True, "परिक्षा")
add("13-138", 13, S13, "OCR", "प्रर्थना", "प्रार्थना", "error", True, "प्रर्थना")
add("13-139", 13, S13, "OCR", "आर्शीवादः", "आशीर्वादः", "error", True, "आर्शीवादः")
add("13-140", 13, S13, "OCR", "स्वास्थ्यम्", "स्वास्थ्यं", "review", False,
    note="Same म्/ं ambiguity as 1-09; not decidable without following-word context.")

S14 = "14. Difficult / Ambiguous Cases"
add("14-141", 14, S14, "Analyze", "रामः गच्छति।", None, "review", True, note=SANDHI_NOTE)
add("14-142", 14, S14, "Analyze sandhi", "रामो गच्छति।", None, "correct", True)
add("14-143", 14, S14, "Possible semantic issue", "देवालयः गच्छति।", None, "review", False,
    note="An inanimate subject (temple) with a motion verb is semantically odd, "
         "but plausibility/semantic checking is out of scope for a grammar/spelling checker.")
add("14-144", 14, S14, "Compound analysis", "राजपुरुषः आगच्छति।", None, "review", True)
add("14-145", 14, S14, "Compound analysis", "महापुरुषः आगच्छति।", None, "review", True)
add("14-146", 14, S14, "Correct", "सः तत् करोति।", None, "correct")
add("14-147", 14, S14, "Correct", "सः तदेव करोति।", None, "correct")
add("14-148", 14, S14, "Compound", "गुरुकुलम् अस्ति।", None, "review", False)
add("14-149", 14, S14, "Compound", "धर्मक्षेत्रम् अस्ति।", None, "review", False)
add("14-150", 14, S14, "Unknown → review", "असामान्यशब्दः", None, "review")

assert len(cases) == 150, f"expected 150 cases, got {len(cases)}"

OUT.parent.mkdir(parents=True, exist_ok=True)
OUT.write_text(
    json.dumps({"_comment": "Gold evaluation matrix for the Sanskrit proof-checker. "
                             "See scripts/build_gold_dataset.py for provenance and rationale.",
                "cases": cases}, ensure_ascii=False, indent=2),
    encoding="utf-8",
)
print(f"wrote {len(cases)} cases to {OUT}")
