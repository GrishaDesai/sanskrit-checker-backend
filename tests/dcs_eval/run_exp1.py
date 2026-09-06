# -*- coding: utf-8 -*-
"""
Runs Experiment 1 (false-positive stress test) sentences through the
UNMODIFIED SanskritEngine and records full output. Does not touch app/*.py.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from app.sanskrit_engine import SanskritEngine  # noqa: E402

DATA_DIR = ROOT / "app" / "vidyut-data"
engine = SanskritEngine(DATA_DIR)

cases = json.loads((HERE / "exp1_candidates.json").read_text(encoding="utf-8"))
print(f"loaded {len(cases)} Experiment 1 candidates")

results = []
n_fp = 0
n_review_only = 0
n_clean = 0

for c in cases:
    text = c["text_deva"]
    result = engine.check_text(text)

    error_tokens = [t for t in result.tokens if t.status != "valid" and t.severity == "error"]
    review_tokens = [t for t in result.tokens if t.status != "valid" and t.severity == "review"]
    # Syntax issues are tiered like token flags: only an error-severity one
    # is a false positive. A review-tier agreement finding (ambiguous
    # morphology) is offered for judgement, not asserted as a defect.
    syntax_issues = [i for i in result.syntax_issues if i.severity == "error"]
    review_issues = [i for i in result.syntax_issues if i.severity != "error"]

    is_fp = bool(error_tokens) or bool(syntax_issues)
    has_review = bool(review_tokens) or bool(review_issues)

    if is_fp:
        n_fp += 1
    elif has_review:
        n_review_only += 1
    else:
        n_clean += 1

    results.append({
        "folder": c["folder"], "file": c["file"], "chapter": c["chapter"],
        "sent_id": c["sent_id"],
        "text_iast": c["text_iast"], "text_deva": text,
        "is_false_positive": is_fp,
        "has_review_flag": has_review,
        "error_tokens": [
            {"text": t.text_deva, "status": t.status, "analysis": t.analysis,
             "suggestion": t.suggestion, "rule": t.rule}
            for t in error_tokens
        ],
        "review_tokens": [
            {"text": t.text_deva, "status": t.status, "analysis": t.analysis,
             "suggestion": t.suggestion, "sandhi_issue": t.sandhi_issue}
            for t in review_tokens
        ],
        "syntax_issues": [
            {"token_text": i.token_text, "issue_type": i.issue_type, "title": i.title,
             "description": i.description, "suggested_text": i.suggested_text,
             "rule_sutra": i.rule_sutra}
            for i in syntax_issues
        ],
        "token_count": len(result.tokens),
        "error_count": result.error_count,
        "review_count": result.review_count,
        "syntax_error_count": result.syntax_error_count,
    })

total = len(cases)
print(f"\nTOTAL sentences tested: {total}")
print(f"False positives (>=1 error-severity flag or syntax_issue): {n_fp}  ({n_fp/total:.1%})")
print(f"Review-only (no hard error, but >=1 review flag): {n_review_only}  ({n_review_only/total:.1%})")
print(f"Fully clean (no flags at all): {n_clean}  ({n_clean/total:.1%})")

(HERE / "experiment1_sample.json").write_text(
    json.dumps({
        "summary": {
            "total_sentences": total,
            "false_positives": n_fp,
            "false_positive_rate": n_fp / total,
            "review_only": n_review_only,
            "review_rate": n_review_only / total,
            "fully_clean": n_clean,
        },
        "results": results,
    }, ensure_ascii=False, indent=1),
    encoding="utf-8"
)
print("\nwrote experiment1_sample.json")
