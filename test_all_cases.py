import sys
sys.stdout.reconfigure(encoding="utf-8")

from app.sanskrit_engine import SanskritEngine

engine = SanskritEngine("sanskrit-checker-backend/vidyut-data")

test_cases = [
    "राम वनं गच्छति।",
    "रामः वनं गच्छति।",
    "रामो वनं गच्छति।",
    "विध्यार्थी पठति।",
    "विद्यार्थी पठति।",
    "बालिका जलम् पिबति।",
    "बालकः पठति।",
    "रामो गच्छति गमति।",
]

for s in test_cases:
    res = engine.check_text(s)
    print(f"==========================================")
    print(f"Sentence: {s}")
    print(f"Tokens ({len(res.tokens)}), Errors ({res.error_count}), Sandhi ({res.sandhi_error_count})")
    for t in res.tokens:
        print(f"  [{t.text_deva}]: status={t.status}, is_valid={t.is_valid}, sug={t.suggestion}, rule={t.rule}")
        if t.sandhi_issue:
            print(f"    Sandhi Note: {t.sandhi_issue}")
