# -*- coding: utf-8 -*-
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
tree = json.loads((HERE / "files_tree.json").read_text(encoding="utf-8"))["tree"]

INCLUDE = [
    "Nyāyasūtra", "Nyāyabhāṣya", "Vaiśeṣikasūtra", "Vaiśeṣikasūtravṛtti",
    "Yogasūtra", "Yogasūtrabhāṣya", "Tattvavaiśāradī", "Pāśupatasūtra",
    "Pañcārthabhāṣya", "Śivasūtra", "Śivasūtravārtika", "Mīmāṃsāsūtrabhāṣya",
    "Sāṃkhyakārikābhāṣya", "Sāṃkhyatattvakaumudī", "Prasannapadā", "Nyāyabindu",
    "Tarkasaṃgraha", "Sarvadarśanasaṃgraha", "Arthaśāstra", "Kāmasūtra",
    "Kāśikāvṛtti", "Mugdhāvabodhinī", "Nirukta", "Kāvyālaṃkāravṛtti",
    "Commentary on the Kāvyālaṃkāravṛtti", "Rājamārtaṇḍa",
    "Abhidharmakośabhāṣya", "Viṃśatikāvṛtti", "Carakasaṃhitā", "Suśrutasaṃhitā",
    "Aṣṭāṅgahṛdayasaṃhitā", "Aṣṭāṅgasaṃgraha", "Indu (ad AHS)",
    "Carakatattvapradīpikā", "Spandakārikānirṇaya",
]

# top-level folder = first path segment
by_folder = {}
for entry in tree:
    if entry["type"] != "blob":
        continue
    path = entry["path"]
    parts = path.split("/", 1)
    if len(parts) != 2:
        continue
    folder, rest = parts
    if folder in INCLUDE:
        by_folder.setdefault(folder, []).append((rest, entry["size"], entry["sha"]))

print(f"whitelist size: {len(INCLUDE)}, folders found in corpus: {len(by_folder)}")
missing = [f for f in INCLUDE if f not in by_folder]
print("NOT FOUND in corpus (name mismatch?):", missing)

total_files = sum(len(v) for v in by_folder.values())
print("total .conllu files across included folders:", total_files)

for folder in sorted(by_folder):
    files = by_folder[folder]
    print(f"  {folder}: {len(files)} files")

(HERE / "included_files_index.json").write_text(
    json.dumps(by_folder, ensure_ascii=False, indent=1), encoding="utf-8"
)
print("wrote included_files_index.json")
