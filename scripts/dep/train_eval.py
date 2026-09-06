# -*- coding: utf-8 -*-
"""Step 3: train a UDPipe-1 parser on UD_Sanskrit-UFAL and report UAS/LAS.

Deployment-realistic mode: parser ONLY. Tokenisation and morphology come from
our own Vidyut pipeline, so the model is trained and scored with GOLD
tokenisation and GOLD tags. UDPipe's own tokenizer/tagger are disabled.

At 230 sentences a single held-out split is noise; the headline number is
k-fold cross-validation over contiguous blocks (contiguous, not shuffled, so
adjacent sentences of the same fable cannot leak across the split).
"""
import io, os, sys, time, argparse, collections
import ufal.udpipe as u
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from job_metrics import JobScores

def read_blocks(path):
    """Return list of raw CoNLL-U sentence blocks (text), preserving comments."""
    blocks, cur = [], []
    for line in io.open(path, encoding="utf-8"):
        if line.strip() == "":
            if cur: blocks.append("".join(cur)); cur = []
        else:
            cur.append(line)
    if cur: blocks.append("".join(cur))
    return blocks

def to_sentences(text):
    inp = u.InputFormat.newInputFormat("conllu")
    inp.setText(text)
    out, s, err = u.Sentences(), u.Sentence(), u.ProcessingError()
    while inp.nextSentence(s, err):
        out.append(s); s = u.Sentence()
    if err.occurred(): raise RuntimeError(err.message)
    return out

def train_model(train_text, heldout_text, parser_opts, path):
    err = u.ProcessingError()
    model = u.Trainer.train(
        "morphodita_parsito",
        to_sentences(train_text),
        to_sentences(heldout_text) if heldout_text else u.Sentences(),
        u.Trainer.NONE,          # tokenizer: ours
        u.Trainer.NONE,          # tagger: Vidyut's
        parser_opts,
        err,
    )
    if err.occurred(): raise RuntimeError(err.message)
    with open(path, "wb") as f:
        f.write(model if isinstance(model, bytes) else model.encode("utf-8"))
    return path

def score(model_path, gold_text):
    """UAS/LAS from gold tokenisation + gold tags, plus per-deprel recall."""
    m = u.Model.load(model_path)
    if m is None: raise RuntimeError("could not load " + model_path)
    err = u.ProcessingError()
    pl = u.Pipeline(m, "conllu", u.Pipeline.NONE, u.Pipeline.DEFAULT, "conllu")

    # strip gold HEAD/DEPREL before parsing
    stripped = []
    for line in gold_text.split("\n"):
        if line.startswith("#") or line.strip() == "":
            stripped.append(line); continue
        c = line.split("\t")
        if len(c) == 10 and "-" not in c[0] and "." not in c[0]:
            c[6], c[7] = "_", "_"
        stripped.append("\t".join(c))
    pred_text = pl.process("\n".join(stripped), err)
    if err.occurred(): raise RuntimeError(err.message)

    def rows(t):
        out = []
        for line in t.split("\n"):
            if line.startswith("#") or not line.strip(): continue
            c = line.split("\t")
            if len(c) == 10 and "-" not in c[0] and "." not in c[0]: out.append(c)
        return out

    g, p = rows(gold_text), rows(pred_text)
    assert len(g) == len(p), "token misalignment %d vs %d" % (len(g), len(p))
    n = uas = las = 0
    per = collections.defaultdict(lambda: [0, 0, 0])  # gold, correct(labelled+head), pred
    for gr, pr in zip(g, p):
        n += 1
        head_ok = gr[6] == pr[6]
        lab_ok = head_ok and gr[7] == pr[7]
        uas += head_ok; las += lab_ok
        per[gr[7]][0] += 1
        per[gr[7]][1] += lab_ok
        per[pr[7]][2] += 1
    return dict(n=n, uas=100.0*uas/n, las=100.0*las/n, per=per, pred_text=pred_text)

def kfold(blocks, k, parser_opts, workdir, verbose=True, extra_train="", only_fold=None):
    N = len(blocks)
    bounds = [round(i*N/k) for i in range(k+1)]
    accum = collections.defaultdict(lambda: [0, 0, 0])
    tot_n = tot_uas = tot_las = 0
    fold_scores = []
    jobs = JobScores()
    for i in range(k):
        if only_fold is not None and i != only_fold: continue
        lo, hi = bounds[i], bounds[i+1]
        test = blocks[lo:hi]
        train = blocks[:lo] + blocks[hi:]
        tr_text = "\n".join(train) + "\n"
        if extra_train: tr_text = extra_train + "\n" + tr_text
        te_text = "\n".join(test) + "\n"
        mp = os.path.join(workdir, "fold%d.udpipe" % i)
        t0 = time.time()
        train_model(tr_text, "", parser_opts, mp)
        r = score(mp, te_text)
        fold_scores.append((r["uas"], r["las"]))
        tot_n += r["n"]; tot_uas += r["uas"]*r["n"]/100.0; tot_las += r["las"]*r["n"]/100.0
        jobs.add(te_text, r["pred_text"])
        for d, (gn, gc, pn) in r["per"].items():
            accum[d][0] += gn; accum[d][1] += gc; accum[d][2] += pn
        if verbose:
            print("  fold %2d: train %3d sents / test %2d sents, %4d tok -> UAS %5.1f  LAS %5.1f  (%.1fs)"
                  % (i, len(train), len(test), r["n"], r["uas"], r["las"], time.time()-t0))
    return dict(n=tot_n, uas=100.0*tot_uas/tot_n, las=100.0*tot_las/tot_n,
                per=accum, folds=fold_scores, jobs=jobs)

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/treebanks/UD_Sanskrit-UFAL/sa_ufal-ud-test.conllu")
    ap.add_argument("--folds", type=int, default=10)
    ap.add_argument("--parser-opts", default=u.Trainer.DEFAULT)
    ap.add_argument("--workdir", default=os.environ.get("DEP_WORK", "."))
    ap.add_argument("--tag", default="UDPipe1 parser, default opts")
    ap.add_argument("--extra-train", default="", help="conllu file prepended to every fold's training set")
    ap.add_argument("--only-fold", type=int, default=None, help="run a single fold (for expensive configs)")
    a = ap.parse_args()
    if not os.path.isdir(a.workdir): os.makedirs(a.workdir)

    blocks = read_blocks(a.data)
    print("treebank: %s" % a.data)
    print("sentences: %d" % len(blocks))
    print("config  : %s" % a.tag)
    print("parser opts: %r" % (a.parser_opts or "<udpipe defaults>"))
    print("\n%d-fold cross-validation (contiguous blocks, gold tokenisation + gold tags):" % a.folds)
    t0 = time.time()
    extra = ""
    if a.extra_train:
        extra = io.open(a.extra_train, encoding="utf-8").read()
        ntok = sum(1 for l in extra.splitlines() if l.strip() and not l.startswith("#"))
        print("extra training data: %s (%d token lines)" % (a.extra_train, ntok))
    r = kfold(blocks, a.folds, a.parser_opts, a.workdir,
              extra_train=extra, only_fold=a.only_fold)
    print("\n  ---- MICRO-AVERAGE over %d tokens ----" % r["n"])
    print("  UAS %.2f%%   LAS %.2f%%   (total %.0fs)" % (r["uas"], r["las"], time.time()-t0))
    uu = sorted(x[0] for x in r["folds"]); ll = sorted(x[1] for x in r["folds"])
    print("  per-fold UAS range %.1f - %.1f ; LAS range %.1f - %.1f" % (uu[0], uu[-1], ll[0], ll[-1]))
    print("\n  per-relation (gold count / labelled-correct / recall / predicted count):")
    for d, (gn, gc, pn) in sorted(r["per"].items(), key=lambda kv: -kv[1][0])[:18]:
        print("    %-14s gold %4d  correct %4d  R %5.1f%%   pred %4d" % (d, gn, gc, 100.0*gc/gn if gn else 0, pn))
    print("")
    print("  ==== STEP 4 ACCEPTANCE TEST: THE TWO NAMED JOBS ====")
    print(r["jobs"].report())
    print("")
    print("  post-verbal subject misses (word / gold rel / gold head -> pred rel / pred head):")
    for w, gr, gh, pr_, ph in r["jobs"].post_misses:
        print("    %-12s %-11s %-12s -> %-11s %s" % (w, gr, gh, pr_, ph))
    print("")
    print("  spurious coordination pairs (job-(b) precision errors):")
    for aa, bb in r["jobs"].coord_fp:
        print("    %s + %s" % (aa, bb))

    print("\n  KEY RELATIONS FOR THIS PHASE:")
    for d in ("nsubj", "nsubj:pass", "conj", "cc"):
        gn, gc, pn = r["per"].get(d, [0,0,0])
        print("    %-14s gold %4d  correct %4d  R %5.1f%%   pred %4d" % (d, gn, gc, 100.0*gc/gn if gn else 0, pn))
