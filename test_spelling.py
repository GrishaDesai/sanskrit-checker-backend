import sys
sys.stdout.reconfigure(encoding="utf-8")

from app.sanskrit_engine import SanskritEngine
from vidyut.lipi import Scheme, transliterate

engine = SanskritEngine("sanskrit-checker-backend/vidyut-data")

def get_spelling_suggestions(slp1_word, engine):
    substitutions = [
        ("Dy", "dy", "'द्य' (द् + य) should be used instead of 'ध्य' (ध् + य)"),
        ("S", "z", "'ष' should be used instead of 'श'"),
        ("z", "S", "'श' should be used instead of 'ष'"),
        ("s", "S", "'श' should be used instead of 'स'"),
        ("s", "z", "'ष' should be used instead of 'स'"),
        ("n", "R", "'ण' should be used instead of 'न'"),
        ("R", "n", "'न' should be used instead of 'ण'"),
        ("b", "v", "'व' should be used instead of 'ब'"),
        ("v", "b", "'ब' should be used instead of 'व'"),
        ("ri", "f", "'ऋ' should be used instead of 'रि'"),
    ]
    
    for old, new, reason in substitutions:
        if old in slp1_word:
            cand = slp1_word.replace(old, new)
            is_val, lemma, ana, underlying, _, _ = engine.check_word(cand)
            if is_val:
                cand_deva = transliterate(cand, Scheme.Slp1, Scheme.Devanagari)
                return cand_deva, "Orthographic / Spelling Correction (वर्ण-शुद्धिः)", reason
    return None, None, None

test_words = ["viDyArTI", "viDyA", "viDyAlayaH", "doSaH", "fSiH"]
for tw in test_words:
    sug, rule, reason = get_spelling_suggestions(tw, engine)
    deva = transliterate(tw, Scheme.Slp1, Scheme.Devanagari)
    print(f"{deva} ({tw}) -> Suggestion: {sug} | Rule: {rule} | Reason: {reason}")
