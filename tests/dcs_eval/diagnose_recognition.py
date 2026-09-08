# -*- coding: utf-8 -*-
"""
Diagnostic (read-only): measures the unrecognized-token rate on the
Experiment-1 DCS sample and attributes every unrecognized token to a
mechanism, so a fix can be aimed at a measured cause rather than a guess.
"""
import json, sys, collections
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from vidyut.lipi import Scheme, transliterate           # noqa: E402
from app.sanskrit_engine import SanskritEngine, WORD_PATTERN  # noqa: E402

engine = SanskritEngine(ROOT / "app" / "vidyut-data")
cases = json.loads((HERE / "exp1_candidates.json").read_text(encoding="utf-8"))

total = unrec = 0
buckets = collections.Counter()
examples = collections.defaultdict(list)
unrec_forms = collections.Counter()

for c in cases:
    for w_deva in WORD_PATTERN.findall(c["text_deva"]):
        s = transliterate(w_deva, Scheme.Devanagari, Scheme.Slp1)
        total += 1
        # Ask the same question the product asks.
        #
        # This previously called `engine._is_recognized`, which consults the
        # lexicons only. `check_word` is the real recognition path and accepts
        # two further classes on top of that: a तिङन्त that VerbGrammar derives
        # from the Dhātupāṭha, and an अव्ययीभाव/उपसर्ग compound recognised from
        # its members. Those are recognised by the engine and reported as valid
        # to the user, so counting them as unrecognized overstated the rate --
        # this is where the 30.6% here and the 30.4% everywhere else came from.
        # The pipeline figure is the authoritative one; this diagnostic was the
        # outlier.
        if engine.check_word(s)[0]:
            continue
        unrec += 1
        unrec_forms[s] += 1
        toks = engine._chedaka.run(s)
        n = len(toks)
        known = [t for t in toks if t.data is not None]
        if n == 1 and known:
            b = "A1_cheda_single_known"          # cheda knows it, we don't
        elif n >= 2 and len(known) == n:
            b = f"A4_cheda_split_all_known_{min(n,4)}"
        elif n >= 2:
            b = "cheda_split_partly_unknown"
        elif s and s[-1] in "dbgjqDBGJQ":
            b = "A2_voiced_final"
        else:
            b = "cheda_no_analysis"
        buckets[b] += 1
        if len(examples[b]) < 12:
            examples[b].append((w_deva, s, [t.text for t in toks]))

print(f"tokens: {total}   unrecognized: {unrec}  ({unrec/total:.1%})")
print(f"distinct unrecognized forms: {len(unrec_forms)}")
print("\nattribution:")
for b, n in buckets.most_common():
    print(f"  {b:34} {n:5}  ({n/unrec:.1%} of unrecognized, {n/total:.1%} of all)")
print("\nexamples:")
for b, _ in buckets.most_common():
    print(f"\n[{b}]")
    for w, s, parts in examples[b]:
        print(f"   {w}   {s}   -> {parts}")

# how many unrecognized tokens end in a voiced stop (A2 target), regardless of bucket
vd = [f for f in unrec_forms if f and f[-1] in "dbgjqDBGJQ"]
print(f"\nunrecognized forms ending in a voiced stop (A2 candidates): {len(vd)} distinct, "
      f"{sum(unrec_forms[f] for f in vd)} occurrences")
print("  ", vd[:20])
