# -*- coding: utf-8 -*-
"""Transliterate UD_Sanskrit-Vedic (IAST) into Devanagari so it can be used as
extra training data for a parser tested on UD_Sanskrit-UFAL (Devanagari).

Only FORM and LEMMA are converted; annotation is untouched. Offline, via
vidyut.lipi -- no new dependency.
"""
import io, sys
from vidyut.lipi import transliterate, Scheme

def tr(x):
    if x == "_" or not x: return x
    return transliterate(x, Scheme.Iast, Scheme.Devanagari)

def convert(src, dst):
    n = 0
    with io.open(src, encoding="utf-8") as f, io.open(dst, "w", encoding="utf-8") as o:
        for line in f:
            if line.startswith("# text ="):
                o.write("# text = " + tr(line.split("=", 1)[1].strip()) + "\n"); continue
            if line.startswith("#") or not line.strip():
                o.write(line); continue
            c = line.rstrip("\n").split("\t")
            if len(c) == 10:
                c[1], c[2] = tr(c[1]), tr(c[2]); n += 1
            o.write("\t".join(c) + "\n")
    return n

if __name__ == "__main__":
    print("converted %d token lines -> %s" % (convert(sys.argv[1], sys.argv[2]), sys.argv[2]))
