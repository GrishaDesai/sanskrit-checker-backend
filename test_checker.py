import sys
sys.stdout.reconfigure(encoding="utf-8")

from app.sanskrit_engine import SanskritEngine
from app.schemas import CheckRequest
from app.main import check_text, load_engine
import app.main as main_mod

load_engine()

sentences = [
    ("रामो गच्छति", 0, 0),
    ("सः पुस्तकम् पठति", 0, 0),
    ("बालकः पठति", 0, 0),
    ("रामो गच्छति गमति", 1, 0),
    ("बालकः गमति", 2, 1),
    ("बालिका जलम् पिबति", 0, 0),
    ("रामः गच्छति", 1, 1),
]

for s, exp_err, exp_sandhi in sentences:
    res = check_text(CheckRequest(text=s))
    print(f"Test '{s}': Tokens: {res.token_count}, Errors: {res.error_count}, Sandhi: {res.sandhi_error_count}")
    for t in res.tokens:
        print(f"  Token: {t.text} | Status: {t.status} | Suggestion: {t.suggestion} | Rule: {t.rule}")
    assert res.error_count == exp_err, f"Mismatch in errors for {s}: expected {exp_err}, got {res.error_count}"
    assert res.sandhi_error_count == exp_sandhi, f"Mismatch in sandhi for {s}: expected {exp_sandhi}, got {res.sandhi_error_count}"

print("\n>>> ALL TESTS PASSED WITH 100% ACCURACY! <<<")
