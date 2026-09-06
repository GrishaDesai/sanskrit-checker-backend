# -*- coding: utf-8 -*-
"""How good are the tags the parser would actually get in deployment?

The cross-validation scores the parser with GOLD tags. In the product the tags
come from vidyut.kosha via the bridge. This measures the gap directly: run the
bridge over UFAL's own sentences and compare its UPOS/FEATS against UD gold.

Any deficit here compounds with the parser's own error rate, so the CV numbers
are an upper bound on deployment, not an estimate of it.
"""
import io, sys, os, collections
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from app.sanskrit_engine import SanskritEngine
from vidyut_conllu import sentence_to_conllu

def gold_sents(path):
    out, cur, text = [], [], None
    for line in io.open(path, encoding="utf-8"):
        if line.startswith("# text ="):
            text = line.split("=", 1)[1].strip()
        if not line.strip():
            if cur: out.append((text, cur)); cur, text = [], None
            continue
        if line.startswith("#"): continue
        c = line.rstrip("\n").split("\t")
        if len(c) == 10 and "-" not in c[0] and "." not in c[0] and c[3] != "PUNCT": cur.append(c)
    if cur: out.append((text, cur))
    return out

# The bridge can only emit NOUN/VERB/PRON/ADV/X, so a strict UPOS comparison
# penalises it for gold distinctions it never had the vocabulary to make
# (ADJ vs NOUN, PROPN vs NOUN, DET vs PRON). The coarse mapping compares what
# the bridge is actually claiming: nominal vs verbal vs pronominal vs
# indeclinable.
COARSE = {"NOUN": "NOM", "PROPN": "NOM", "ADJ": "NOM", "NUM": "NOM",
          "PRON": "PRO", "DET": "PRO",
          "VERB": "VRB", "AUX": "VRB",
          "ADV": "IND", "PART": "IND", "CCONJ": "IND", "SCONJ": "IND",
          "ADP": "IND", "INTJ": "IND", "X": "X", "PUNCT": "P"}

def feat(f, k):
    for p in f.split("|"):
        if p.startswith(k + "="): return p.split("=", 1)[1]
    return None

if __name__ == "__main__":
    eng = SanskritEngine("app/vidyut-data")
    sents = gold_sents(sys.argv[1] if len(sys.argv)>1 else "data/treebanks/UD_Sanskrit-UFAL/sa_ufal-ud-test.conllu")
    n = aligned = 0
    upos_ok = 0
    coarse_ok = 0
    ours_X = 0
    import collections as _c
    conf = _c.Counter()
    stats = {k: [0, 0, 0] for k in ("Case", "Gender", "Number")}  # gold-has, we-emit, correct
    unspec_all = 0
    skipped = 0
    engine_failed = 0
    for text, rows in sents:
        if not text: skipped += 1; continue
        try:
            res = eng.check_text(text)
        except Exception:
            skipped += 1; continue      # engine cannot analyse this sentence at all
        toks = res.tokens
        if len(toks) != len(rows):
            skipped += 1; continue      # tokenisation differs (MWT splits); not comparable
        conllu, _ = sentence_to_conllu(toks, text=text)
        ours = [l.split("\t") for l in conllu.split("\n")
                if l and not l.startswith("#") and len(l.split("\t")) == 10]
        aligned += 1
        for g, o in zip(rows, ours):
            n += 1
            upos_ok += (g[3] == o[3])
            coarse_ok += (COARSE.get(g[3], g[3]) == COARSE.get(o[3], o[3]))
            if o[3] == "X": ours_X += 1
            if COARSE.get(g[3],g[3]) != COARSE.get(o[3],o[3]): conf[(g[3], o[3])] += 1
            if o[5] == "_": unspec_all += 1
            for k in stats:
                gv, ov = feat(g[5], k), feat(o[5], k)
                if gv: stats[k][0] += 1
                if ov: stats[k][1] += 1
                if gv and ov and gv == ov: stats[k][2] += 1
    print("sentences compared     : %d (of %d; %d skipped on tokenisation mismatch)"
          % (aligned, len(sents), skipped))
    print("tokens compared        : %d" % n)
    print("UPOS agreement         : %.1f%%" % (100.0*upos_ok/n if n else 0))
    print("UPOS agreement (coarse) : %.1f%%   [nominal/verbal/pronominal/indeclinable]"
          % (100.0*coarse_ok/n if n else 0))
    print("bridge emitted X (word unrecognised) : %d  (%.1f%%)" % (ours_X, 100.0*ours_X/n if n else 0))
    print("top coarse disagreements (gold -> bridge):")
    for (a_, b_), c_ in conf.most_common(8):
        print("    %-8s -> %-6s %4d" % (a_, b_, c_))
    print("FEATS entirely empty   : %d  (%.1f%% of tokens the parser sees with NO morphology)"
          % (unspec_all, 100.0*unspec_all/n if n else 0))
    for k, (gh, oe, ok) in stats.items():
        print("  %-7s gold has %4d | bridge emits %4d | agree %4d  -> recall %.1f%%, precision %.1f%%"
              % (k, gh, oe, ok, 100.0*ok/gh if gh else 0, 100.0*ok/oe if oe else 0))
