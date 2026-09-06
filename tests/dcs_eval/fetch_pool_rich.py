# -*- coding: utf-8 -*-
"""
Same file selection as fetch_pool.py (same RNG seed -> same 226 files), but
this time keeps full per-token data: FORM, LEMMA, UPOS, FEATS, and whether
the token is a "standalone" word (its ID is a plain integer not covered by
any multi-word "N-M" range row) plus the Unsandhied/UnsandhiedReconstructed
MISC fields, so later scripts can safely locate a target word inside the
`# text` continuous surface string and know whether external sandhi already
altered its ending.
"""
import json
import random
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
INDEX = json.loads((HERE / "included_files_index.json").read_text(encoding="utf-8"))
RAW_BASE = "https://raw.githubusercontent.com/OliverHellwig/sanskrit/master/dcs/data/conllu/files"

random.seed(20260905)
MAX_PER_FOLDER = 10
MIN_SIZE = 400
MAX_SIZE = 60000

chosen = []
for folder, files in INDEX.items():
    real_files = [(rest, size, sha) for rest, size, sha in files
                  if not rest.endswith("_parsed") and MIN_SIZE <= size <= MAX_SIZE]
    random.shuffle(real_files)
    for rest, size, sha in real_files[:MAX_PER_FOLDER]:
        chosen.append((folder, rest, size))

print(f"chosen {len(chosen)} files")


def fetch(folder: str, rest: str) -> str:
    path = f"{folder}/{rest}"
    quoted = "/".join(urllib.parse.quote(seg) for seg in path.split("/"))
    url = f"{RAW_BASE}/{quoted}"
    req = urllib.request.Request(url, headers={"User-Agent": "dcs-eval-research/1.0"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8")


UNSANDHIED_RE = re.compile(r"Unsandhied=([^|]*)")
RECON_RE = re.compile(r"UnsandhiedReconstructed=([^|]*)")


def parse_conllu(raw: str, folder: str, rest: str) -> list[dict]:
    sentences = []
    cur_text = None
    cur_chapter = None
    cur_sent_id = None
    cur_rows = []       # all rows (incl. range headers) for current sentence
    range_covered = set()

    def flush():
        if cur_text and cur_sent_id:
            tokens = []
            for cols in cur_rows:
                tid = cols[0]
                if "-" in tid:
                    continue  # range header row itself carries no lemma/case
                form = cols[1]
                lemma = cols[2]
                upos = cols[3]
                feats = cols[5]
                misc = cols[9] if len(cols) > 9 else ""
                m = UNSANDHIED_RE.search(misc)
                unsandhied = m.group(1) if m else form
                standalone = tid not in range_covered
                tokens.append({
                    "id": tid, "form": form, "lemma": lemma, "upos": upos,
                    "feats": feats, "unsandhied": unsandhied, "standalone": standalone,
                })
            sentences.append({
                "folder": folder, "file": rest, "chapter": cur_chapter,
                "sent_id": cur_sent_id, "text_iast": cur_text, "tokens": tokens,
            })

    for line in raw.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("## chapter:"):
            cur_chapter = line.split(":", 1)[1].strip()
        elif line.startswith("# text ="):
            cur_text = line.split("=", 1)[1].strip()
        elif line.startswith("# sent_id"):
            cur_sent_id = line.split("=", 1)[1].strip()
        elif line.strip() == "":
            flush()
            cur_text = None
            cur_sent_id = None
            cur_rows = []
            range_covered = set()
        elif line and not line.startswith("#"):
            cols = line.split("\t")
            if len(cols) < 10:
                continue
            tid = cols[0]
            if "-" in tid:
                a, b = tid.split("-")
                for k in range(int(a), int(b) + 1):
                    range_covered.add(str(k))
            cur_rows.append(cols)
    flush()
    return sentences


all_sentences = []
errors = 0
for i, (folder, rest, size) in enumerate(chosen):
    try:
        raw = fetch(folder, rest)
    except Exception as e:
        errors += 1
        print(f"  ERROR fetching {folder}/{rest}: {e}")
        continue
    sents = parse_conllu(raw, folder, rest)
    all_sentences.extend(sents)
    if i % 30 == 0:
        print(f"  [{i}/{len(chosen)}] {folder} -> total {len(all_sentences)}")
    time.sleep(0.03)

print(f"TOTAL sentences pooled: {len(all_sentences)} (errors: {errors})")
(HERE / "sentence_pool_rich.json").write_text(
    json.dumps(all_sentences, ensure_ascii=False), encoding="utf-8"
)
print("wrote sentence_pool_rich.json")
