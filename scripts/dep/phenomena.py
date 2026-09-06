# -*- coding: utf-8 -*-
"""How much evidence does a treebank carry for the two named jobs?
 (a) post-verbal subjects   (b) coordination of nominals
"""
import io, sys, collections
sys.path.insert(0, "scripts/dep")
from conllu_stats import read

def analyse(path, label):
    sents = read(path)
    pre = post = 0
    post_examples = []
    coord_nom = 0            # conj pairs where both are nominals
    coord_diff_gender = 0    # ... and gender differs (the FP-shaped case)
    coord_examples = []
    for meta, rows in sents:
        toks = {}
        for r in rows:
            if "-" in r[0] or "." in r[0]: continue
            toks[int(r[0])] = r
        for i, r in toks.items():
            if r[7] in ("nsubj", "nsubj:pass"):
                h = int(r[6])
                if h == 0: continue
                if i > h:
                    post += 1
                    if len(post_examples) < 12:
                        post_examples.append((meta.get("text", ""), r[1], toks[h][1]))
                else:
                    pre += 1
            if r[7] == "conj":
                h = int(r[6])
                if h == 0 or h not in toks: continue
                a, b = toks[h], r
                if a[3] in ("NOUN","PROPN","PRON","ADJ","NUM") and b[3] in ("NOUN","PROPN","PRON","ADJ","NUM"):
                    coord_nom += 1
                    fa = dict(x.split("=",1) for x in a[5].split("|") if "=" in x)
                    fb = dict(x.split("=",1) for x in b[5].split("|") if "=" in x)
                    ga, gb = fa.get("Gender"), fb.get("Gender")
                    if ga and gb and ga != gb:
                        coord_diff_gender += 1
                        if len(coord_examples) < 12:
                            coord_examples.append((meta.get("text",""), a[1], ga, b[1], gb))
    tot = pre + post
    print("="*62); print(label); print("="*62)
    print("JOB (a) subject position, of %d nsubj/nsubj:pass with a real head:" % tot)
    print("   subject BEFORE its verb-head : %4d  (%.1f%%)" % (pre, 100.0*pre/tot if tot else 0))
    print("   subject AFTER  its verb-head : %4d  (%.1f%%)   <-- the job-(a) cases" % (post, 100.0*post/tot if tot else 0))
    print("\n   post-verbal examples (subject / head):")
    for t, s, h in post_examples:
        print("     %-10s <- %-12s | %s" % (s, h, t[:58]))
    print("\nJOB (b) coordination:")
    print("   conj pairs where both members are nominal      : %d" % coord_nom)
    print("   ... of those, with DIFFERING gender            : %d   <-- the FP-shaped cases" % coord_diff_gender)
    print("\n   differing-gender coordination examples:")
    for t, a, ga, b, gb in coord_examples:
        print("     %s(%s) + %s(%s) | %s" % (a, ga, b, gb, t[:52]))

if __name__ == "__main__":
    analyse(sys.argv[1], sys.argv[2] if len(sys.argv)>2 else sys.argv[1])
