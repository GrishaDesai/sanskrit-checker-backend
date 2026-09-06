# -*- coding: utf-8 -*-
"""Project UD_Sanskrit-UFAL down onto SURFACE tokens.

The treebank annotates syntactic words (compounds split, sandhi resolved);
our engine emits surface tokens. This collapses every multiword-token range
into the single surface node the engine would actually produce, so the
training data has the shape the product can supply.

Collapsing rule: within a range a-b, the "head member" is the member whose
HEAD lies outside the range (the one attaching the whole group into the
sentence). The collapsed node inherits that member's head and deprel; any
child of any member that lies outside the range is re-pointed at the
collapsed node; arcs internal to the range disappear with it.
"""
import io, sys, collections

def sentences(path):
    out, cur = [], []
    for line in io.open(path, encoding="utf-8"):
        if not line.strip():
            if cur: out.append(cur); cur = []
            continue
        cur.append(line.rstrip("\n"))
    if cur: out.append(cur)
    return out

def collapse(block):
    comments = [l for l in block if l.startswith("#")]
    rows = [l.split("\t") for l in block if not l.startswith("#") and len(l.split("\t")) == 10]
    ranges, words = [], {}
    for c in rows:
        if "-" in c[0]:
            a, b = c[0].split("-"); ranges.append((int(a), int(b), c[1]))
        elif "." not in c[0]:
            words[int(c[0])] = c
    if not words: return None
    covered = {}
    for a, b, form in ranges:
        for i in range(a, b + 1): covered[i] = (a, b, form)

    # new node list in surface order
    new_nodes, seen = [], set()
    for i in sorted(words):
        if i in covered:
            a, b, form = covered[i]
            if a in seen: continue
            seen.add(a)
            members = [words[j] for j in range(a, b + 1) if j in words]
            outside = [m for m in members if int(m[6]) < a or int(m[6]) > b]
            head_member = outside[0] if outside else members[0]
            new_nodes.append({"ids": list(range(a, b + 1)), "form": form,
                              "lemma": head_member[2], "upos": head_member[3],
                              "feats": head_member[5], "head": int(head_member[6]),
                              "deprel": head_member[7]})
        else:
            c = words[i]
            new_nodes.append({"ids": [i], "form": c[1], "lemma": c[2], "upos": c[3],
                              "feats": c[5], "head": int(c[6]), "deprel": c[7]})

    old2new = {}
    for n_i, nd in enumerate(new_nodes, 1):
        for old in nd["ids"]: old2new[old] = n_i
    out = list(comments)
    for n_i, nd in enumerate(new_nodes, 1):
        h = nd["head"]
        nh = 0 if h == 0 else old2new.get(h, 0)
        if nh == n_i: nh = 0                      # self-loop after collapse -> root
        out.append("\t".join([str(n_i), nd["form"], nd["lemma"], nd["upos"], "_",
                              nd["feats"], str(nh), nd["deprel"], "_", "_"]))
    # exactly one root
    roots = [i for i, nd in enumerate(new_nodes, 1) if (0 if nd["head"] == 0 else old2new.get(nd["head"], 0)) == 0]
    if len(roots) != 1:
        fixed, first = [], True
        for line in out:
            if line.startswith("#"): fixed.append(line); continue
            c = line.split("\t")
            if c[6] == "0":
                if first: c[7] = "root"; first = False
                else: c[6] = str(roots[0]); c[7] = "dep" if c[7] == "root" else c[7]
            fixed.append("\t".join(c))
        out = fixed
    return out

if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    n_out = n_tok = 0
    with io.open(dst, "w", encoding="utf-8") as o:
        for b in sentences(src):
            c = collapse(b)
            if not c: continue
            n_out += 1
            n_tok += sum(1 for l in c if not l.startswith("#"))
            o.write("\n".join(c) + "\n\n")
    print("wrote %d sentences / %d surface tokens -> %s" % (n_out, n_tok, dst))
