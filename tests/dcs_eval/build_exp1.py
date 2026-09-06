# -*- coding: utf-8 -*-
"""
Builds the Experiment-1 (false-positive stress test) sample: a disjoint
subset of natural, unmodified DCS prose sentences from the whitelisted
classical-prose folders, reconstructed from the CoNLL-U `# text = ...` line
(the actual continuous surface text, sandhi included -- see REPORT.md for
the sandhi-split finding), transliterated to Devanagari.
"""
import json
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))

from vidyut.lipi import Scheme, transliterate  # noqa: E402

pool = json.loads((HERE / "sentence_pool_rich.json").read_text(encoding="utf-8"))
print(f"pool size: {len(pool)}")

IAST_OK_RE = re.compile(r"^[a-zA-Zāīūṛṝḷḹēōṃḥṅñṭḍṇśṣ'\s]+$")


def is_clean(text: str) -> bool:
    if not IAST_OK_RE.match(text):
        return False
    if "'" in text:  # avagraha corner case -- excluded for simplicity, see REPORT.md
        return False
    n_words = len(text.split())
    return 4 <= n_words <= 22


clean = [s for s in pool if is_clean(s["text_iast"])]
print(f"clean (script-only, 4-22 words, no avagraha): {len(clean)}")

# Dedup by exact text (DCS occasionally repeats stock phrases/mantras)
seen = set()
deduped = []
for s in clean:
    if s["text_iast"] in seen:
        continue
    seen.add(s["text_iast"])
    deduped.append(s)
print(f"after dedup: {len(deduped)}")

random.seed(20260905)
random.shuffle(deduped)

N_EXP1 = 260
exp1_raw = deduped[:N_EXP1]
remainder = deduped[N_EXP1:]   # strictly disjoint pool reserved for Experiment 2

print(f"Experiment 1 candidate sentences: {len(exp1_raw)}")
print(f"Remaining pool reserved for Experiment 2: {len(remainder)}")

for s in exp1_raw:
    s["text_deva"] = transliterate(s["text_iast"], Scheme.Iast, Scheme.Devanagari)

(HERE / "exp1_candidates.json").write_text(
    json.dumps(exp1_raw, ensure_ascii=False, indent=1), encoding="utf-8"
)
(HERE / "exp2_pool.json").write_text(
    json.dumps(remainder, ensure_ascii=False, indent=1), encoding="utf-8"
)
print("wrote exp1_candidates.json and exp2_pool.json")

# quick spot-check print
for s in exp1_raw[:5]:
    print("-", s["folder"], "|", s["text_iast"], "->", s["text_deva"])
