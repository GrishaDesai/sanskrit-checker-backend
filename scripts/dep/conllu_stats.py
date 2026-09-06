# -*- coding: utf-8 -*-
"""Honest size/shape stats for a CoNLL-U treebank."""
import io, sys, collections

def read(path):
    sents, cur, meta = [], [], {}
    for line in io.open(path, encoding="utf-8"):
        line = line.rstrip("\n")
        if not line.strip():
            if cur: sents.append((meta, cur)); cur, meta = [], {}
            continue
        if line.startswith("#"):
            if "=" in line:
                k, v = line[1:].split("=", 1); meta[k.strip()] = v.strip()
            continue
        cur.append(line.split("\t"))
    if cur: sents.append((meta, cur))
    return sents

def stats(path, label):
    sents = read(path)
    n_sent = len(sents)
    syn = mwt = empty = 0
    deprels = collections.Counter(); upos = collections.Counter()
    lens = []
    for meta, rows in sents:
        s = 0
        for r in rows:
            i = r[0]
            if "-" in i: mwt += 1; continue
            if "." in i: empty += 1; continue
            syn += 1; s += 1
            deprels[r[7]] += 1; upos[r[3]] += 1
        lens.append(s)
    lens.sort()
    print("=" * 62)
    print(label)
    print("=" * 62)
    print("sentences              : %d" % n_sent)
    print("syntactic words (tokens): %d" % syn)
    print("multiword-token ranges : %d" % mwt)
    print("empty nodes            : %d" % empty)
    if lens:
        print("sentence length: mean %.1f  median %d  min %d  max %d"
              % (sum(lens)/len(lens), lens[len(lens)//2], lens[0], lens[-1]))
    print("distinct deprels       : %d" % len(deprels))
    print("\ntop deprels:")
    for d, c in deprels.most_common(20):
        print("   %-14s %6d  %5.1f%%" % (d, c, 100.0*c/syn))
    print("\nkey relations for this phase:")
    for d in ("nsubj", "nsubj:pass", "conj", "cc", "obj", "root", "amod", "flat"):
        print("   %-14s %6d" % (d, deprels.get(d, 0)))
    print("\nUPOS:")
    for d, c in upos.most_common(20):
        print("   %-8s %6d" % (d, c))
    return sents

if __name__ == "__main__":
    stats(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else sys.argv[1])
