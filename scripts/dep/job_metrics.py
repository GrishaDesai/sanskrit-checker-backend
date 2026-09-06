# -*- coding: utf-8 -*-
"""Step 4 acceptance metrics: the TWO NAMED JOBS, not aggregate LAS.

LAS is stricter than what these checks need, and in one case more forgiving.
So both jobs are scored on their own terms:

 (a) post-verbal subject identification
     The Vidyut layer already finds pre-verbal subjects. The parser only has
     to earn its keep on subjects that FOLLOW their verb. Scored as: of the
     gold subjects that are post-verbal, how many does the parser attach to
     the right verb with a subject label. Also reports nsubj PRECISION,
     because a check gated on a spurious subject is a new false positive.

 (b) coordination detection
     The check does not need conj's exact head, only the question "are these
     two nominals in one coordination?" So coordination is scored as
     membership in the transitive closure over conj arcs, pairwise.
     Precision matters more than recall here: this gate SUPPRESSES a gender
     flag, so a false coordination silently hides a real error, while a
     missed coordination merely leaves today's false positive in place.
"""
import collections

NOMINAL = {"NOUN", "PROPN", "PRON", "ADJ", "NUM"}
SUBJ = {"nsubj", "nsubj:pass", "nsubj:cop"}

def rows_by_sent(text):
    sents, cur = [], []
    for line in text.split("\n"):
        if not line.strip():
            if cur: sents.append(cur); cur = []
            continue
        if line.startswith("#"): continue
        c = line.split("\t")
        if len(c) == 10 and "-" not in c[0] and "." not in c[0]:
            cur.append(c)
    if cur: sents.append(cur)
    return sents

def coord_groups(rows):
    """Transitive closure over conj arcs -> list of frozensets of indices."""
    parent = {int(r[0]): int(r[0]) for r in rows}
    def find(x):
        while parent[x] != x: parent[x] = parent[parent[x]]; x = parent[x]
        return x
    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb: parent[ra] = rb
    for r in rows:
        if r[7] == "conj":
            h = int(r[6])
            if h in parent: union(int(r[0]), h)
    g = collections.defaultdict(set)
    for i in parent: g[find(i)].add(i)
    return [frozenset(v) for v in g.values() if len(v) > 1]

def coord_pairs(rows, nominal_only=True):
    pairs = set()
    upos = {int(r[0]): r[3] for r in rows}
    for grp in coord_groups(rows):
        members = sorted(grp)
        for i, a in enumerate(members):
            for b in members[i+1:]:
                if nominal_only and not (upos.get(a) in NOMINAL and upos.get(b) in NOMINAL):
                    continue
                pairs.add((a, b))
    return pairs

class JobScores(object):
    def __init__(self):
        self.post_gold = self.post_head_ok = self.post_full_ok = 0
        self.pre_gold = self.pre_full_ok = 0
        self.subj_pred = self.subj_pred_ok = 0
        self.cp_gold = self.cp_pred = self.cp_hit = 0
        self.post_misses = []
        self.coord_fp = []

    def add(self, gold_text, pred_text):
        gs, ps = rows_by_sent(gold_text), rows_by_sent(pred_text)
        assert len(gs) == len(ps)
        for g, p in zip(gs, ps):
            gi = {int(r[0]): r for r in g}
            pi = {int(r[0]): r for r in p}
            # ---- job (a)
            for i, r in gi.items():
                if r[7] not in SUBJ: continue
                h = int(r[6])
                if h == 0: continue
                pr = pi[i]
                full_ok = (pr[6] == r[6] and pr[7] == r[7])
                if i > h:                       # post-verbal
                    self.post_gold += 1
                    self.post_head_ok += (pr[6] == r[6])
                    self.post_full_ok += full_ok
                    if not full_ok and len(self.post_misses) < 15:
                        self.post_misses.append((r[1], r[7], gi[h][1],
                                                 pr[7], gi.get(int(pr[6]), ["","(root)"])[1]))
                else:
                    self.pre_gold += 1
                    self.pre_full_ok += full_ok
            for i, pr in pi.items():
                if pr[7] in SUBJ:
                    self.subj_pred += 1
                    self.subj_pred_ok += (gi[i][7] == pr[7] and gi[i][6] == pr[6])
            # ---- job (b)
            gp, pp = coord_pairs(g), coord_pairs(p)
            self.cp_gold += len(gp); self.cp_pred += len(pp); self.cp_hit += len(gp & pp)
            for a, b in sorted(pp - gp):
                if len(self.coord_fp) < 15:
                    self.coord_fp.append((gi[a][1], gi[b][1]))

    def report(self):
        L = []
        A = L.append
        A("  JOB (a) SUBJECT IDENTIFICATION")
        A("    pre-verbal  subjects: %4d gold, %4d exactly right  (%.1f%%)"
          % (self.pre_gold, self.pre_full_ok, pct(self.pre_full_ok, self.pre_gold)))
        A("    POST-verbal subjects: %4d gold, %4d exactly right  (%.1f%%)  <-- the job"
          % (self.post_gold, self.post_full_ok, pct(self.post_full_ok, self.post_gold)))
        A("       (right verb attached, any subject label: %d / %.1f%%)"
          % (self.post_head_ok, pct(self.post_head_ok, self.post_gold)))
        A("    subject PRECISION  : %4d predicted, %4d correct   (%.1f%%)"
          % (self.subj_pred, self.subj_pred_ok, pct(self.subj_pred_ok, self.subj_pred)))
        A("  JOB (b) COORDINATION (nominal pairs, transitive closure over conj)")
        A("    gold pairs %4d | predicted %4d | correct %4d" % (self.cp_gold, self.cp_pred, self.cp_hit))
        A("    precision %.1f%%   recall %.1f%%   <-- precision is the one that matters"
          % (pct(self.cp_hit, self.cp_pred), pct(self.cp_hit, self.cp_gold)))
        return "\n".join(L)

def pct(a, b):
    return 100.0 * a / b if b else 0.0
