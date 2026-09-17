# -*- coding: utf-8 -*-
"""
C1 (read-only): does the compound-shape check separate real compounds from
junk splits? See docs/vidyut-phase-scope.md §10.4.

For every token the product leaves unrecognised on the Experiment-1 DCS
sample, take Chedaka's split and apply the shape check from सुपो
धातुप्रातिपदिकयोः (२.४.७१): every non-final piece must be a bare प्रातिपदिक,
and the final piece must be a recognised pada.

Scored against DCS's own segmentation where it can be recovered without
guessing. The candidate file keeps DCS tokens flat (multiword ranges were
dropped when it was built) but keeps `standalone`: a standalone token is
exactly one surface word, so a run of non-standalone tokens lying between two
anchors belongs to the surface words between them. Only a gap holding exactly
one surface word is scored; the rest are reported as unaligned, never
guessed.

Changes nothing in the product. Usage:
    python tests/dcs_eval/c1_shape_check.py [--json out.json]
"""
import argparse
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from vidyut.lipi import Scheme, transliterate  # noqa: E402
from app.sanskrit_engine import SanskritEngine  # noqa: E402

engine = SanskritEngine(ROOT / "app" / "vidyut-data")
kosha = engine._kosha
chedaka = engine._chedaka


# ---- the check under test ---------------------------------------------------

def lemmas(form: str) -> set:
    out = set()
    for e in kosha.get(form):
        pe = getattr(e, "pratipadika_entry", None)
        lemma = getattr(pe, "lemma", None) if pe else None
        if lemma:
            out.add(lemma)
    return out


def is_bare_stem(piece: str) -> bool:
    """The piece is spelled as its own prātipadika. An n-stem appears without
    its n inside a compound (नलोपः प्रातिपदिकान्तस्य ८.२.७: राजन् -> राज-), so
    piece+"n" is accepted as the same stem."""
    if piece in lemmas(piece):
        return True
    return (piece + "n") in lemmas(piece + "n")


def is_pada(piece: str) -> bool:
    return bool(list(kosha.get(piece))) or engine.check_word(piece)[0]


def shape(pieces: list) -> str:
    if len(pieces) < 2:
        return "no_split"
    if not all(is_pada(p) for p in pieces):
        return "unknown_piece"
    if not is_pada(pieces[-1]):
        return "bad_final"
    bad = [p for p in pieces[:-1] if not is_bare_stem(p)]
    return "compound_shape" if not bad else "non_final_not_stem"


# ---- DCS gold ---------------------------------------------------------------

def slp(iast: str) -> str:
    return transliterate(iast, Scheme.Iast, Scheme.Slp1)


def norm(p: str) -> str:
    """Compare pieces modulo final visarga/anusvāra spelling."""
    if p.endswith("H"):
        p = p[:-1] + "s"
    if p.endswith("M"):
        p = p[:-1] + "m"
    return p


def gold_by_word(case) -> dict:
    """surface-word index -> list of DCS tokens, for unambiguous words only."""
    n_words = len(case["text_iast"].split())
    toks = case["tokens"]
    # Word index of each anchor, counted from the end: the k-th standalone
    # token from the end is the k-th surface word from the end.
    anchors_from = [0] * (len(toks) + 1)
    for j in range(len(toks) - 1, -1, -1):
        anchors_from[j] = anchors_from[j + 1] + (1 if toks[j]["standalone"] else 0)

    out = {}
    w = 0
    run = []
    for j in range(len(toks) + 1):
        if j < len(toks) and not toks[j]["standalone"]:
            run.append(toks[j])
            continue
        next_word = n_words - anchors_from[j]   # word index of this anchor, or n_words at end
        gap = next_word - w
        if run:
            if gap == 1:
                out[w] = run
        elif gap != 0:
            return {}                            # counts do not reconcile
        w = next_word
        run = []
        if j < len(toks):
            out[w] = [toks[j]]
            w += 1
    return out if w == n_words else {}


def gold_class(gtoks) -> str:
    if len(gtoks) == 1:
        return "dcs_single"
    if all("Case=Cpd" in (t["feats"] or "") for t in gtoks[:-1]):
        return "dcs_compound"
    return "dcs_phrase"


def boundaries(pieces):
    out, n = set(), 0
    for p in pieces[:-1]:
        n += len(p)
        out.add(n)
    return out, n + len(pieces[-1])


def split_agreement(ch_pieces, gtoks) -> str:
    g = [norm(slp(t["unsandhied"])) for t in gtoks]
    c = [norm(p) for p in ch_pieces]
    if c == g:
        return "exact"
    cb, cl = boundaries(c)
    gb, gl = boundaries(g)
    if cl != gl:
        return "different"
    if cb <= gb:
        return "coarser"   # every Chedaka boundary is a DCS boundary
    return "different"


# ---- run ---------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default=None)
    args = ap.parse_args()

    cases = json.loads((HERE / "exp1_candidates.json").read_text(encoding="utf-8"))
    rows = []
    unaligned_sentences = 0
    for c in cases:
        result = engine.check_text(c["text_deva"])
        gold = gold_by_word(c)
        if not gold:
            unaligned_sentences += 1
        words = c["text_iast"].split()
        aligned = len(words) == len(result.tokens)
        for i, t in enumerate(result.tokens):
            if not (t.status == "invalid" and t.severity == "review"):
                continue
            pieces = [x.text for x in chedaka.run(t.text_slp1)]
            g = gold.get(i) if aligned else None
            rows.append({
                "sentence": c["text_deva"],
                "word": t.text_deva,
                "slp1": t.text_slp1,
                "pieces": pieces,
                "shape": shape(pieces),
                "gold": None if g is None else [t2["unsandhied"] for t2 in g],
                "gold_class": None if g is None else gold_class(g),
                "split": None if g is None or len(pieces) < 2 else split_agreement(pieces, g),
            })

    print(f"unrecognised review-tier tokens : {len(rows)}")
    print(f"sentences with no usable alignment: {unaligned_sentences}/{len(cases)}")
    by_shape = collections.Counter(r["shape"] for r in rows)
    print("\nshape verdicts:")
    for k, v in by_shape.most_common():
        print(f"  {k:20} {v}")

    scored = [r for r in rows if r["gold_class"] is not None]
    print(f"\nwith DCS gold for the word: {len(scored)}")
    tab = collections.Counter((r["shape"], r["gold_class"]) for r in scored)
    classes = ["dcs_compound", "dcs_phrase", "dcs_single"]
    print(f"  {'shape':20} " + " ".join(f"{c:>13}" for c in classes))
    for s in sorted({r['shape'] for r in scored}):
        print(f"  {s:20} " + " ".join(f"{tab[(s, c)]:>13}" for c in classes))

    acc = [r for r in scored if r["shape"] == "compound_shape"]
    rej = [r for r in scored if r["shape"] != "compound_shape" and r["shape"] != "no_split"]
    def splits(rs):
        return collections.Counter(r["split"] for r in rs)
    print(f"\naccepted as compound (gold known): {len(acc)}  split vs DCS: {dict(splits(acc))}")
    print(f"rejected (gold known)            : {len(rej)}  split vs DCS: {dict(splits(rej))}")

    if args.json:
        Path(args.json).write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwrote {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
