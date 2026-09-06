# -*- coding: utf-8 -*-
"""Train on one treebank, test on ALL of another.

Used for the Vedic option: UD_Sanskrit-Vedic is 88x larger than UFAL but is a
different language stage, a different script (transliterated here) and a
different annotation style. Because the two corpora are disjoint there is no
leakage, so the model can be scored on the WHOLE of UFAL -- the same 1,843
tokens the cross-validation used, making the numbers directly comparable to
C1 rather than to a 23-sentence fold.
"""
import io, os, sys, time, argparse, collections
import ufal.udpipe as u
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from train_eval import read_blocks, train_model, score
from job_metrics import JobScores

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--train-file", required=True)
    ap.add_argument("--test-file", default="data/treebanks/UD_Sanskrit-UFAL/sa_ufal-ud-test.conllu")
    ap.add_argument("--parser-opts", default=u.Trainer.DEFAULT)
    ap.add_argument("--model-out", required=True)
    ap.add_argument("--max-train-sents", type=int, default=0)
    ap.add_argument("--tag", default="external-train")
    a = ap.parse_args()

    tr_blocks = read_blocks(a.train_file)
    if a.max_train_sents: tr_blocks = tr_blocks[:a.max_train_sents]
    te_text = io.open(a.test_file, encoding="utf-8").read()

    print("config    : %s" % a.tag)
    print("train     : %s (%d sentences)" % (a.train_file, len(tr_blocks)))
    print("test      : %s" % a.test_file)
    print("parser opt: %r" % (a.parser_opts or "<udpipe defaults>"))
    t0 = time.time()
    train_model("\n".join(tr_blocks) + "\n", "", a.parser_opts, a.model_out)
    print("trained in %.0fs -> %s" % (time.time()-t0, a.model_out))

    r = score(a.model_out, te_text)
    print("\n---- scored on %d tokens ----" % r["n"])
    print("UAS %.2f%%   LAS %.2f%%" % (r["uas"], r["las"]))
    print("\nper-relation (gold / labelled-correct / recall / predicted):")
    for d, (gn, gc, pn) in sorted(r["per"].items(), key=lambda kv: -kv[1][0])[:16]:
        print("  %-14s gold %4d  correct %4d  R %5.1f%%   pred %4d"
              % (d, gn, gc, 100.0*gc/gn if gn else 0, pn))
    j = JobScores(); j.add(te_text, r["pred_text"])
    print("\n==== STEP 4 ACCEPTANCE TEST ====")
    print(j.report())
