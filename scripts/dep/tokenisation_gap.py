# -*- coding: utf-8 -*-
"""Can our engine even produce the input this treebank's parser expects?

UD_Sanskrit-UFAL is annotated over SYNTACTIC WORDS: compounds are split into
members and sandhi fusions are resolved, with the surface string kept only as
a multiword-token range. Our engine works over surface tokens, because
reliable compound segmentation is the ceiling documented in the Vidyut phase.

If the two tokenisations disagree, a parser trained on this treebank is being
fed input of a kind it never saw, and no amount of parser accuracy fixes that.
This measures how wide the gap is.
"""
import io, sys, os
sys.path.insert(0, os.path.abspath("."))
from app.sanskrit_engine import SanskritEngine

def sents(path):
    out, cur, text, mwt = [], [], None, 0
    for line in io.open(path, encoding="utf-8"):
        if line.startswith("# text ="): text = line.split("=", 1)[1].strip()
        if not line.strip():
            if cur: out.append((text, cur, mwt)); cur, text, mwt = [], None, 0
            continue
        if line.startswith("#"): continue
        c = line.rstrip("\n").split("\t")
        if len(c) != 10: continue
        if "-" in c[0]: mwt += 1; continue
        if "." in c[0]: continue
        if c[3] == "PUNCT": continue   # engine WORD_PATTERN excludes dandas/punctuation by design
        cur.append(c)
    if cur: out.append((text, cur, mwt))
    return out

if __name__ == "__main__":
    eng = SanskritEngine("app/vidyut-data")
    S = sents(sys.argv[1] if len(sys.argv)>1 else "data/treebanks/UD_Sanskrit-UFAL/sa_ufal-ud-test.conllu")
    with_mwt = sum(1 for _, _, m in S if m)
    match = mismatch = failed = 0
    tok_ours = tok_gold = 0
    for text, rows, m in S:
        if not text: failed += 1; continue
        try:
            toks = eng.check_text(text).tokens
        except Exception:
            failed += 1; continue
        tok_ours += len(toks); tok_gold += len(rows)
        if len(toks) == len(rows): match += 1
        else: mismatch += 1
    print("UFAL sentences                          : %d" % len(S))
    print("  containing a multiword-token range    : %d  (%.1f%%)"
          % (with_mwt, 100.0*with_mwt/len(S)))
    print("  engine tokenisation MATCHES gold count: %d  (%.1f%%)"
          % (match, 100.0*match/len(S)))
    print("  engine tokenisation DIFFERS           : %d  (%.1f%%)"
          % (mismatch, 100.0*mismatch/len(S)))
    print("  engine could not analyse at all       : %d" % failed)
    print("total tokens: engine %d vs treebank syntactic words %d  (ratio %.2f)"
          % (tok_ours, tok_gold, (1.0*tok_gold/tok_ours) if tok_ours else 0))
