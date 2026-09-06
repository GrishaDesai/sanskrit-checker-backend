# -*- coding: utf-8 -*-
"""Step 4: the real acceptance test.

Runs the exact sentences behind the Vidyut phase's remaining syntax false
positives (plus the two canonical examples from the phase brief) through the
DEPLOYMENT path -- engine tokenisation + vidyut morphology -> CoNLL-U ->
trained parser -- and asks only the two questions this phase exists to answer:

 (a) does the parser attach the verb's real, post-verbal subject to it?
 (b) does the parser see the coordinated nominals as coordinated?

Aggregate LAS is not the question here; these specific answers are.
"""
import sys, os, argparse, io
sys.path.insert(0, os.path.abspath("."))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ufal.udpipe as u
from app.sanskrit_engine import SanskritEngine
from vidyut_conllu import sentence_to_conllu
from job_metrics import coord_pairs

# (text, job, expectation)
PROBES = [
    # --- job (a): the real subject FOLLOWS the verb -------------------------
    ("वनं गच्छति रामः", "a", ("गच्छति", "रामः"),
     "brief's canonical post-verbal subject"),
    ("उन्मत्तो मूढ इत्येवं मन्यन्ते इतरे जनाः", "a", ("मन्यन्ते", "जनाः"),
     "DCS FP #3 -- subject follows verb, उन्मत्तो is inside the इति-quoted clause"),
    ("स्नातानुलिप्तं यं चापि भजन्ते नीलमक्षिकाः", "a", ("भजन्ते", "नीलमक्षिकाः"),
     "DCS FP #4 -- fronted object, subject follows verb"),
    ("अस्ति दाक्षिणात्ये जनपदे महिलारोप्यं नाम नगरम्", "a", ("अस्ति", "नगरम्"),
     "classic अस्ति-initial existential -- NOTE: this sentence is IN the UFAL "
     "training data, so it tests memorisation, not generalisation"),
    ("पुस्तकं पठति बालकः", "a", ("पठति", "बालकः"),
     "minimal constructed post-verbal subject, held out by construction"),
    # --- job (b): coordinated nominals wrongly paired for gender agreement --
    ("तस्य दण्डः शुल्कं च भवति", "b", ("दण्डः", "शुल्कं"),
     "brief's canonical coordination"),
    ("गणिकादुहितरं प्रकुर्वतश्चतुष्पञ्चाशत्पणो दण्डः शुल्कं मातुर् भोगः षोडशगुणः",
     "b", ("दण्डः", "शुल्कं"), "DCS FP #1 -- coordinate enumeration"),
    ("कक्षौ स्तनौ गलः पृष्ठं जघनम् ऊरू च स्थानानि", "b", ("गलः", "पृष्ठं"),
     "DCS FP #2 -- anatomical enumeration closed by च"),
]

def parse(model, conllu):
    err = u.ProcessingError()
    pl = u.Pipeline(model, "conllu", u.Pipeline.NONE, u.Pipeline.DEFAULT, "conllu")
    out = pl.process(conllu, err)
    if err.occurred(): raise RuntimeError(err.message)
    return out

def rows_of(text):
    out = []
    for line in text.split("\n"):
        if line.startswith("#") or not line.strip(): continue
        c = line.split("\t")
        if len(c) == 10 and "-" not in c[0] and "." not in c[0]: out.append(c)
    return out

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    a = ap.parse_args()
    engine = SanskritEngine("app/vidyut-data")
    model = u.Model.load(a.model)
    if model is None: raise SystemExit("could not load " + a.model)

    tb = io.open("data/treebanks/UD_Sanskrit-UFAL/sa_ufal-ud-test.conllu", encoding="utf-8").read()
    a_pass = a_tot = b_pass = b_tot = 0
    seen_in_train = []
    for text, job, expect, note in PROBES:
        res = engine.check_text(text)
        toks = res.tokens
        conllu, amb = sentence_to_conllu(toks, text=text)
        parsed = parse(model, conllu)
        rows = rows_of(parsed)
        forms = {r[1]: int(r[0]) for r in rows}
        print("=" * 74)
        print(text)
        contaminated = text[:28] in tb
        if contaminated: seen_in_train.append(text)
        print("  (%s)  job (%s), expect: %s%s"
              % (note, job, " <- ".join(expect),
                 "   [!! IN TRAINING DATA]" if contaminated else ""))
        print("  parse:")
        for r in rows:
            h = int(r[6]); hw = "ROOT" if h == 0 else rows[h-1][1]
            print("    %-2s %-16s %-6s %-26s %-10s -> %s"
                  % (r[0], r[1], r[3], r[5][:26], r[7], hw))
        if job == "a":
            a_tot += 1
            verb, subj = expect
            vi, si = forms.get(verb), forms.get(subj)
            ok = False
            if vi and si:
                sr = rows[si-1]
                ok = (int(sr[6]) == vi and sr[7].startswith("nsubj"))
            print("  RESULT job(a): %s%s" % ("PASS" if ok else "FAIL",
                  "  (discounted: memorised)" if contaminated else ""))
            if contaminated: a_tot -= 1
            else: a_pass += ok
        else:
            b_tot += 1
            x, y = expect
            xi, yi = forms.get(x), forms.get(y)
            ok = bool(xi and yi and (min(xi, yi), max(xi, yi)) in coord_pairs(rows, nominal_only=False))
            print("  RESULT job(b): %s%s" % ("PASS" if ok else "FAIL",
                  "  (discounted: memorised)" if contaminated else ""))
            if contaminated: b_tot -= 1
            else: b_pass += ok
    print("=" * 74)
    print("JOB (a) post-verbal subject : %d / %d" % (a_pass, a_tot))
    print("JOB (b) coordination        : %d / %d" % (b_pass, b_tot))
    print("(excluded as present in training data: %d)" % len(seen_in_train))

if __name__ == "__main__":
    main()
