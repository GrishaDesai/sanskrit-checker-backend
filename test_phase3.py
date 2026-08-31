import sys
sys.stdout.reconfigure(encoding="utf-8")

from app.sanskrit_engine import SanskritEngine

engine = SanskritEngine("sanskrit-checker-backend/vidyut-data")

test_cases = [
    "भगवान् भक्तानाम् रक्षति।",
    "भगवान् भक्तान् रक्षति।",
    "अहम् पुस्तकम् पठति।",
    "बालकाः पुस्तकम् पठति।",
    "देवस्य नमः।",
    "देवाय नमः।",
    "राजपुरुषः वनम् गच्छति।",
    "प्रातःकाले सूर्य उदेति।",
]

for s in test_cases:
    res = engine.check_text(s)
    print(f"==========================================")
    print(f"Sentence: {s}")
    print(f"Tokens ({len(res.tokens)}), Total Errors ({res.error_count}), Syntax Errors ({res.syntax_error_count}), Sandhi Errors ({res.sandhi_error_count})")
    for t in res.tokens:
        print(f"  [{t.text_deva}]: status={t.status}, sug={t.suggestion}, rule={t.rule}")
        if t.karaka_issue:
            print(f"    Kāraka/Syntax Note: {t.karaka_issue}")
    if res.compounds:
        for c in res.compounds:
            print(f"  Compound: {c.compound_text} -> {c.compound_type} | Vigraha: {c.vigraha_vakya}")
