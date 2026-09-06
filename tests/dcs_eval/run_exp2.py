# -*- coding: utf-8 -*-
"""
Runs Experiment 2 (recall test) corrupted sentences through the UNMODIFIED
SanskritEngine and computes recall overall and broken out by gap category.
Does not touch app/*.py.
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from app.sanskrit_engine import SanskritEngine  # noqa: E402

DATA_DIR = ROOT / "app" / "vidyut-data"
engine = SanskritEngine(DATA_DIR)

cases = json.loads((HERE / "exp2_corruptions.json").read_text(encoding="utf-8"))
print(f"loaded {len(cases)} Experiment 2 corrupted cases")


def flagged_surfaces(result):
    surfaces = {t.text_deva for t in result.tokens if t.status != "valid" and t.severity == "error"}
    surfaces |= {i.token_text for i in result.syntax_issues if i.severity == "error"}
    return surfaces


results = []
by_bucket = defaultdict(lambda: [0, 0])
by_category = defaultdict(lambda: [0, 0])

for c in cases:
    text = c["corrupted_text_deva"]
    result = engine.check_text(text)
    flagged = flagged_surfaces(result)
    expected_surface = c["expected_flagged_surface_deva"]

    has_any_flag = bool(result.error_count) or any(
        i.severity == "error" for i in result.syntax_issues)
    surface_matched = expected_surface in flagged
    caught = has_any_flag and surface_matched

    bucket = c["gap_bucket"]
    by_bucket[bucket][1] += 1
    by_bucket[bucket][0] += int(caught)
    by_category[c["category"]][1] += 1
    by_category[c["category"]][0] += int(caught)

    results.append({
        "category": c["category"], "gap_bucket": bucket,
        "folder": c["folder"], "file": c["file"], "sent_id": c["sent_id"],
        "original_text_deva": c["original_text_deva"],
        "corrupted_text_deva": text,
        "target_word_original": c["target_word_original"],
        "target_word_corrupted": c["target_word_corrupted"],
        "expected_flagged_surface": expected_surface,
        "note": c["note"],
        "caught": caught,
        "flagged_surfaces": sorted(flagged),
        "error_tokens": [
            {"text": t.text_deva, "status": t.status, "analysis": t.analysis, "suggestion": t.suggestion}
            for t in result.tokens if t.status != "valid" and t.severity == "error"
        ],
        "syntax_issues": [
            {"token_text": i.token_text, "issue_type": i.issue_type, "title": i.title}
            for i in result.syntax_issues
        ],
    })

total = len(cases)
total_caught = sum(r["caught"] for r in results)
print(f"\nOVERALL recall: {total_caught}/{total}  ({total_caught/total:.1%})")
print("\nBy gap bucket:")
for bucket, (caught, n) in by_bucket.items():
    print(f"  {bucket:20} {caught}/{n}  ({caught/n:.1%})")
print("\nBy category:")
for cat, (caught, n) in by_category.items():
    print(f"  {cat:40} {caught}/{n}  ({caught/n:.1%})")

(HERE / "experiment2_sample.json").write_text(
    json.dumps({
        "summary": {
            "total_cases": total,
            "total_caught": total_caught,
            "overall_recall": total_caught / total,
            "by_gap_bucket": {k: {"caught": v[0], "total": v[1], "recall": v[0] / v[1]} for k, v in by_bucket.items()},
            "by_category": {k: {"caught": v[0], "total": v[1], "recall": v[0] / v[1]} for k, v in by_category.items()},
        },
        "results": results,
    }, ensure_ascii=False, indent=1),
    encoding="utf-8"
)
print("\nwrote experiment2_sample.json")
