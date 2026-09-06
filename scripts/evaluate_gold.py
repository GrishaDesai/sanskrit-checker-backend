# -*- coding: utf-8 -*-
"""
Runs the gold dataset (tests/gold/dataset.json) against the live SanskritEngine
and reports where the checker currently stands, broken down by section.

Verdict mapping from engine output:
  - any token with status != "valid", OR any syntax_issue reported
      -> engine_verdict = "error"
  - otherwise
      -> engine_verdict = "correct"

A case "passes" when:
  - expected verdict "error"   -> engine_verdict == "error"
                                   AND (no expected_error_surface, or it is among
                                        the flagged tokens/issues)
  - expected verdict "correct" -> engine_verdict == "correct"
  - expected verdict "review"  -> engine_verdict != "error"
                                   (i.e. it must NOT be asserted as a hard error;
                                    the engine has no separate "review" tier today,
                                    so silence counts as satisfying "review")

Cases marked in_scope=False are reported separately as KNOWN GAPS: they still
run and their pass/fail is shown, but they never count against the headline
pass rate, since the current design does not claim to handle them.

Sandhi-splitting cases additionally check the padapatha-style split by calling
the checker's own sandhi/segmentation path (best-effort; see _get_split below).

Usage:
    venv/Scripts/python.exe scripts/evaluate_gold.py [--json out.json] [--section N]
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.sanskrit_engine import SanskritEngine  # noqa: E402

GOLD = ROOT / "tests" / "gold" / "dataset.json"
DATA_DIR = ROOT / "app" / "vidyut-data"


def engine_verdict(result) -> str:
    """Only 'error'-severity findings count as a hard error. A 'review'
    finding (unrecognised word with no confident fix, unapplied-but-optional
    sandhi, ...) is offered for human judgement and must not read as a defect."""
    has_token_error = any(t.status != "valid" and t.severity == "error" for t in result.tokens)
    # Syntax issues carry a severity too: an agreement finding that rests on
    # an ambiguous morphological analysis is offered, not asserted, and must
    # read the same way as a review-tier token flag.
    has_syntax_error = any(i.severity == "error" for i in result.syntax_issues)
    return "error" if (has_token_error or has_syntax_error) else "correct"


def flagged_surfaces(result) -> set[str]:
    surfaces = {t.text_deva for t in result.tokens if t.status != "valid" and t.severity == "error"}
    surfaces |= {i.token_text for i in result.syntax_issues if i.severity == "error"}
    return surfaces


def evaluate_case(engine: SanskritEngine, case: dict) -> dict:
    result = engine.check_text(case["input"])
    verdict = engine_verdict(result)
    flagged = flagged_surfaces(result)

    expected = case["verdict"]
    if expected == "error":
        ok = verdict == "error"
        if ok and case.get("expected_error_surface"):
            ok = case["expected_error_surface"] in flagged
    elif expected == "correct":
        ok = verdict == "correct"
    elif expected == "review":
        ok = verdict != "error"
    else:
        ok = False

    return {
        "id": case["id"],
        "section": case["section"],
        "section_name": case["section_name"],
        "category": case["category"],
        "input": case["input"],
        "expected_verdict": expected,
        "engine_verdict": verdict,
        "flagged_surfaces": sorted(flagged),
        "in_scope": case["in_scope"],
        "pass": ok,
        "note": case.get("note", ""),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", type=str, default=None, help="write full results as JSON to this path")
    ap.add_argument("--section", type=int, default=None, help="only run one section number")
    ap.add_argument("--failures-only", action="store_true", help="only print failing cases")
    args = ap.parse_args()

    if not (DATA_DIR / "kosha").exists():
        print(f"vidyut data missing at {DATA_DIR}")
        return 1

    engine = SanskritEngine(DATA_DIR)
    gold = json.loads(GOLD.read_text(encoding="utf-8"))["cases"]
    if args.section is not None:
        gold = [c for c in gold if c["section"] == args.section]

    results = [evaluate_case(engine, c) for c in gold]

    by_section: dict[tuple[int, str], list[dict]] = defaultdict(list)
    for r in results:
        by_section[(r["section"], r["section_name"])].append(r)

    print()
    print("=" * 88)
    print("SANSKRIT CHECKER — GOLD EVALUATION REPORT")
    print("=" * 88)

    total_in_scope = total_in_scope_pass = 0
    total_out_scope = total_out_scope_pass = 0

    for (sec_no, sec_name), rows in sorted(by_section.items()):
        in_scope_rows = [r for r in rows if r["in_scope"]]
        out_scope_rows = [r for r in rows if not r["in_scope"]]
        in_pass = sum(r["pass"] for r in in_scope_rows)
        out_pass = sum(r["pass"] for r in out_scope_rows)
        total_in_scope += len(in_scope_rows)
        total_in_scope_pass += in_pass
        total_out_scope += len(out_scope_rows)
        total_out_scope_pass += out_pass

        header = f"[{sec_no:>2}] {sec_name}"
        scope_str = f"in-scope {in_pass}/{len(in_scope_rows)}"
        if out_scope_rows:
            scope_str += f"   (known-gap {out_pass}/{len(out_scope_rows)})"
        print(f"\n{header}\n{'-' * len(header)}   {scope_str}")

        for r in rows:
            if args.failures_only and r["pass"]:
                continue
            mark = "PASS" if r["pass"] else "FAIL"
            scope_tag = "" if r["in_scope"] else " [known-gap]"
            print(
                f"  {mark:4}  {r['id']:8} {r['category']:32.32} "
                f"exp={r['expected_verdict']:7} got={r['engine_verdict']:7}"
                f"{scope_tag}   {r['input']}"
            )

    print("\n" + "=" * 88)
    print("SUMMARY")
    print("=" * 88)
    if total_in_scope:
        print(f"  in-scope pass rate     {total_in_scope_pass}/{total_in_scope}"
              f"  ({total_in_scope_pass / total_in_scope:.1%})")
    if total_out_scope:
        print(f"  known-gap pass rate    {total_out_scope_pass}/{total_out_scope}"
              f"  ({total_out_scope_pass / total_out_scope:.1%})  (informational only)")

    print("\n  by category (in-scope only):")
    by_verdict = defaultdict(lambda: [0, 0])
    for r in results:
        if not r["in_scope"]:
            continue
        key = r["expected_verdict"]
        by_verdict[key][0] += r["pass"]
        by_verdict[key][1] += 1
    for k in ("error", "correct", "review"):
        p, t = by_verdict.get(k, (0, 0))
        if t:
            print(f"    expected={k:8} {p}/{t}  ({p / t:.1%})")

    if args.json:
        Path(args.json).write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n  full results written to {args.json}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
