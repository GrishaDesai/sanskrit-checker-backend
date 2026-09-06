# -*- coding: utf-8 -*-
"""
Builds Experiment 2 (recall test) corruptions on a DISJOINT DCS sample
(exp2_pool.json, reserved by build_exp1.py) targeting the two known recall
gaps named in the brief:

  (a) karaka/case-role errors beyond simple object-in-wrong-case:
      - transitive-verb object put in a WRONG case that ISN'T Ṣaṣṭhī
        (karaka_syntax.py's TRANSITIVE_DHATU_MAP check only tests is_sasthi)
      - caturthi-dhatu / panchami-dhatu upapada argument put in a wrong
        non-Sasthi case (same is_sasthi-only gate)
      - subject put in an oblique case instead of Prathama (the subject-
        finder heuristic in analyze_sentence() requires Prathama-like
        markers, so an oblique-case "subject" is never even found)
  (b) multi-letter (2-edit) spelling typos, which defeat check_word()'s
      single-edit-distance spelling corrector (_find_spelling_correction),
      so the token is left at "review" severity instead of "error".

For each corruption we record: source sentence, target word, category,
original case/vibhakti, corrupted case/vibhakti, and the expected flagged
surface -- the ground truth a human grammarian would assert.

This script does NOT import or touch app/*.py except read-only calls to
SanskritEngine._is_recognized() used purely to validate that a corrupted
typo candidate is not itself a real word (test-construction sanity check,
not an engine modification).
"""
import json
import random
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))

from vidyut.lipi import Scheme, transliterate  # noqa: E402
from vidyut.prakriya import Vyakarana, Pada, Vibhakti, Vacana  # noqa: E402
from app.sanskrit_engine import SanskritEngine  # noqa: E402

DATA_DIR = ROOT / "app" / "vidyut-data"
engine = SanskritEngine(DATA_DIR)
_vyakarana = Vyakarana()

random.seed(20260906)

pool = json.loads((HERE / "exp2_pool.json").read_text(encoding="utf-8"))
print(f"Experiment-2 disjoint pool: {len(pool)} sentences")

# CoNLL-U Case feature -> vidyut Vibhakti. Construction below re-derives the
# real inflected surface form via Vyakarana().derive() (the same mechanism
# karaka_syntax.py's own _case_form() uses) rather than a hand-rolled suffix
# table -- a naive "+ena" table is WRONG for any stem containing r/ṛ/ṣ, which
# retroflexes the ending to "+eṇa" (ṇatva, Panini 8.4.1); re-deriving through
# vidyut's own engine gets this right for every stem class automatically.
CASE_TO_VIBHAKTI = {
    "Nom": Vibhakti.Prathama, "Acc": Vibhakti.Dvitiya, "Ins": Vibhakti.Trtiya,
    "Dat": Vibhakti.Caturthi, "Abl": Vibhakti.Panchami, "Gen": Vibhakti.Sasthi,
    "Loc": Vibhakti.Saptami,
}
GENDER_NAMES = {"Masc": "Pum", "Fem": "Stri", "Neut": "Napumsaka"}

TRANSITIVE_LEMMAS = {"rakṣ", "paṭh", "gam", "khād", "likh", "pā", "dṛś", "paś",
                      "tyaj", "sev", "kṛ", "nī", "han", "smṛ"}
CATURTHI_LEMMAS = {"ruc", "dā", "yam", "krudh", "kup", "īrṣy"}
PANCHAMI_LEMMAS = {"bhī", "trā", "pramad"}
UPAPADA_WORDS_INS = {"saha", "sākam", "sārdham", "alam"}   # require Trtiya
UPAPADA_WORDS_DAT = {"namas", "namaḥ", "svasti"}            # require Caturthi

VERB_UPOS = {"VERB"}


def feats_dict(feats: str) -> dict:
    d = {}
    if not feats:
        return d
    for kv in feats.split("|"):
        if "=" in kv:
            k, v = kv.split("=", 1)
            d[k] = v
    return d


def to_slp1(iast: str) -> str:
    return transliterate(iast, Scheme.Iast, Scheme.Slp1)


def to_deva(slp1: str) -> str:
    return transliterate(slp1, Scheme.Slp1, Scheme.Devanagari)


def find_case_swap(token, new_case) -> tuple[str, str] | None:
    """Given a leaf token dict with Case/Gender/Number features naming a
    singular a-stem/A-stem-class nominal, re-derive its surface form in
    `new_case` via a genuine Vyakarana().derive() call on the SAME
    pratipadika/linga vidyut's own Kosha recognises for this word -- exactly
    the mechanism karaka_syntax.py's _case_form() uses internally -- rather
    than a hand-rolled suffix table, so natva/sandhi are handled correctly
    for every stem instead of guessed. Returns (new_form_iast, orig_case) or
    None if the word isn't found as an unambiguous singular nominal in the
    Kosha matching the DCS-tagged case, or has no Eka-vacana derivation."""
    feats = feats_dict(token["feats"])
    gender = feats.get("Gender")
    number = feats.get("Number")
    case = feats.get("Case")
    if number != "Sing" or gender not in ("Masc", "Fem", "Neut") or not case:
        return None
    if case not in CASE_TO_VIBHAKTI or new_case not in CASE_TO_VIBHAKTI:
        return None
    if token["form"] != token["unsandhied"]:
        return None  # external sandhi already altered the ending -- skip

    orig_slp1 = to_slp1(token["form"])
    orig_vibhakti = CASE_TO_VIBHAKTI[case]
    linga_name = GENDER_NAMES[gender]

    entries = [e for e in engine._raw_kosha_entries(orig_slp1)
               if type(e).__name__.endswith("Subanta")]
    for entry in entries:
        if entry.vibhakti != orig_vibhakti or entry.linga.name != linga_name:
            continue
        try:
            args = entry.to_prakriya_args()
            # sanity check: re-deriving the SAME (original) vibhakti must
            # reproduce the attested surface form, or this is the wrong
            # homograph/stem for this token.
            check_sub = Pada.Subanta(pratipadika=args.pratipadika, linga=args.linga,
                                      vibhakti=orig_vibhakti, vacana=Vacana.Eka)
            check_forms = {r.text for r in _vyakarana.derive(check_sub)}
            if orig_slp1 not in check_forms:
                continue
            new_sub = Pada.Subanta(pratipadika=args.pratipadika, linga=args.linga,
                                    vibhakti=CASE_TO_VIBHAKTI[new_case], vacana=Vacana.Eka)
            new_forms = sorted({r.text for r in _vyakarana.derive(new_sub)})
        except Exception:
            continue
        if not new_forms:
            continue
        new_slp1 = new_forms[0]
        if new_slp1 == orig_slp1:
            continue  # syncretic (e.g. neuter Nom==Acc) -- not a visible corruption
        return transliterate(new_slp1, Scheme.Slp1, Scheme.Iast), case
    return None


def unique_word_index(text_iast: str, form: str) -> int | None:
    words = text_iast.split()
    idxs = [i for i, w in enumerate(words) if w == form]
    return idxs[0] if len(idxs) == 1 else None


def apply_word_swap(text_iast: str, form: str, new_form: str) -> str | None:
    idx = unique_word_index(text_iast, form)
    if idx is None:
        return None
    words = text_iast.split()
    words[idx] = new_form
    return " ".join(words)


# -- corruption pass 1: karaka-role subtypes --------------------------------
used_sent_idx = set()
karaka_cases = []

CATEGORY_DEFS = [
    # (name, lemma_set, source_case, target_case, requires "before verb")
    ("object_wrong_noncase_instrumental", TRANSITIVE_LEMMAS, "Acc", "Ins", True),
    ("caturthi_wrong_noncase_accusative", CATURTHI_LEMMAS, "Dat", "Acc", True),
    ("panchami_wrong_noncase_accusative", PANCHAMI_LEMMAS, "Abl", "Acc", True),
]

for cat_name, lemma_set, src_case, tgt_case, need_verb_after in CATEGORY_DEFS:
    for si, s in enumerate(pool):
        if si in used_sent_idx:
            continue
        toks = s["tokens"]
        # find a verb token with matching lemma
        verb_idx = None
        for t in toks:
            if t["upos"] in VERB_UPOS and t["lemma"] in lemma_set:
                verb_idx = int(t["id"])
                break
        if verb_idx is None:
            continue
        # find an eligible noun token of src_case before the verb
        target = None
        for t in toks:
            if not t["standalone"]:
                continue
            if int(t["id"]) >= verb_idx:
                continue
            feats = feats_dict(t["feats"])
            if feats.get("Case") != src_case:
                continue
            swap = find_case_swap(t, tgt_case)
            if swap:
                target = (t, swap)
                break
        if not target:
            continue
        t, (new_form_slp1_src_is_iast, orig_case) = target
        new_form_iast = new_form_slp1_src_is_iast  # find_case_swap works in IAST-suffix space (ASCII SLP1-ish but reusing IAST stem)
        corrupted_text_iast = apply_word_swap(s["text_iast"], t["form"], new_form_iast)
        if not corrupted_text_iast:
            continue
        used_sent_idx.add(si)
        karaka_cases.append({
            "category": cat_name, "gap_bucket": "karaka_role",
            "sentence_index": si, "folder": s["folder"], "file": s["file"],
            "sent_id": s["sent_id"], "original_text_iast": s["text_iast"],
            "corrupted_text_iast": corrupted_text_iast,
            "target_word_original": t["form"], "target_word_corrupted": new_form_iast,
            "original_case": src_case, "corrupted_case": tgt_case,
            "note": f"'{t['form']}' ({src_case}) -> '{new_form_iast}' ({tgt_case}); "
                    f"engine's karaka check for this verb only tests for a wrongly-Ṣaṣṭhī "
                    f"argument, so a non-Ṣaṣṭhī wrong case is expected to slip through.",
        })
        if sum(1 for c in karaka_cases if c["category"] == cat_name) >= 60:
            break

print(f"karaka dhatu-triggered corruptions so far: {len(karaka_cases)}")
for cat_name, *_ in CATEGORY_DEFS:
    print(" ", cat_name, sum(1 for c in karaka_cases if c["category"] == cat_name))

# -- corruption pass 1b: upapada-adjunct wrong non-Sasthi case ---------------
# 'saha'/'sākam'/'sārdham'/'alam' require Trtiya on the preceding noun;
# 'namas'/'svasti' require Caturthi. The engine's UPAPADA_VIBHAKTI_MAP check
# only tests whether the preceding noun is wrongly Ṣaṣṭhī, so swapping a
# genuinely-required Trtiya/Caturthi noun into some OTHER wrong case (Dvitiya)
# is expected to slip through undetected.
upapada_defs = [
    (UPAPADA_WORDS_INS, "Ins", "Acc"),
    (UPAPADA_WORDS_DAT, "Dat", "Acc"),
]
for word_set, src_case, tgt_case in upapada_defs:
    for si, s in enumerate(pool):
        if si in used_sent_idx:
            continue
        toks = s["tokens"]
        upapada_idx = None
        for t in toks:
            if t["standalone"] and t["form"].rstrip("ḥ") in {w.rstrip("ḥ").rstrip("s") for w in word_set} \
                    or t["lemma"] in word_set:
                upapada_idx = int(t["id"])
                break
        if upapada_idx is None:
            continue
        target = None
        for t in toks:
            if not t["standalone"] or int(t["id"]) >= upapada_idx:
                continue
            feats = feats_dict(t["feats"])
            if feats.get("Case") != src_case:
                continue
            swap = find_case_swap(t, tgt_case)
            if swap:
                target = (t, swap)
        if not target:
            continue
        t, (new_form_iast, orig_case) = target
        corrupted_text_iast = apply_word_swap(s["text_iast"], t["form"], new_form_iast)
        if not corrupted_text_iast:
            continue
        used_sent_idx.add(si)
        karaka_cases.append({
            "category": "upapada_wrong_noncase", "gap_bucket": "karaka_role",
            "sentence_index": si, "folder": s["folder"], "file": s["file"],
            "sent_id": s["sent_id"], "original_text_iast": s["text_iast"],
            "corrupted_text_iast": corrupted_text_iast,
            "target_word_original": t["form"], "target_word_corrupted": new_form_iast,
            "original_case": src_case, "corrupted_case": tgt_case,
            "note": f"'{t['form']}' ({src_case}) -> '{new_form_iast}' ({tgt_case}); the "
                    f"upapada-vibhakti check only tests for a wrongly-Ṣaṣṭhī argument, so a "
                    f"non-Ṣaṣṭhī wrong case is expected to slip through.",
        })

print(f"karaka dhatu+upapada-triggered corruptions after pass 1b: {len(karaka_cases)}")

# -- corruption pass 2: subject-case error (Nom -> Ins), any finite verb -----
subject_cases = []
for si, s in enumerate(pool):
    if si in used_sent_idx:
        continue
    if len(subject_cases) >= 80:
        break
    toks = s["tokens"]
    verb_idx = None
    for t in toks:
        if t["upos"] in VERB_UPOS:
            verb_idx = int(t["id"])
            break
    if verb_idx is None:
        continue
    target = None
    for t in toks:
        if not t["standalone"] or int(t["id"]) >= verb_idx:
            continue
        feats = feats_dict(t["feats"])
        if feats.get("Case") != "Nom":
            continue
        swap = find_case_swap(t, "Ins")
        if swap:
            target = (t, swap)
            break
    if not target:
        continue
    t, (new_form_iast, orig_case) = target
    corrupted_text_iast = apply_word_swap(s["text_iast"], t["form"], new_form_iast)
    if not corrupted_text_iast:
        continue
    used_sent_idx.add(si)
    subject_cases.append({
        "category": "subject_wrong_case_instrumental", "gap_bucket": "karaka_role",
        "sentence_index": si, "folder": s["folder"], "file": s["file"],
        "sent_id": s["sent_id"], "original_text_iast": s["text_iast"],
        "corrupted_text_iast": corrupted_text_iast,
        "target_word_original": t["form"], "target_word_corrupted": new_form_iast,
        "original_case": "Nom", "corrupted_case": "Ins",
        "note": f"'{t['form']}' (Nom, the grammatical subject) -> '{new_form_iast}' (Ins); "
                f"the engine's subject-finder requires a Prathama-like marker, so an "
                f"oblique-case 'subject' is never identified and no check fires at all.",
    })

print(f"subject-case corruptions: {len(subject_cases)}")

# -- corruption pass 3: multi-letter (2-edit) spelling typos -----------------
random_letters_conso = list("kKgGNcCjJYwWqQRtTdDnpPbBmyrlvSzsh")
random_letters_vowel = list("aAiIuUfxeEoO")

def two_edit_corrupt(slp1_word: str) -> str | None:
    n = len(slp1_word)
    if n < 5:
        return None
    positions = random.sample(range(1, n), min(2, n - 1))  # avoid touching position 0
    chars = list(slp1_word)
    for pos in positions:
        orig = chars[pos]
        pool_letters = random_letters_vowel if orig in "aAiIuUfxeEoO" else random_letters_conso
        choices = [c for c in pool_letters if c != orig]
        chars[pos] = random.choice(choices)
    return "".join(chars)


def levenshtein(a: str, b: str) -> int:
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
        prev = cur
    return prev[-1]


typo_cases = []
attempts = 0
for si, s in enumerate(pool):
    if si in used_sent_idx:
        continue
    if len(typo_cases) >= 100:
        break
    toks = s["tokens"]
    candidates = [t for t in toks if t["standalone"] and t["form"] == t["unsandhied"]
                  and len(to_slp1(t["form"])) >= 5 and t["upos"] in ("NOUN", "VERB", "ADJ")]
    if not candidates:
        continue
    random.shuffle(candidates)
    chosen_target = None
    corrupted_slp1 = None
    for t in candidates:
        orig_slp1 = to_slp1(t["form"])
        if not engine._is_recognized(orig_slp1):
            continue  # DCS lemmatization edge case; need a real recognised "before" state
        ok = False
        for _ in range(5):
            cand = two_edit_corrupt(orig_slp1)
            attempts += 1
            if cand is None:
                break
            if levenshtein(orig_slp1, cand) < 2:
                continue
            if engine._is_recognized(cand):
                continue  # accidentally landed on another real word; try again
            corrupted_slp1 = cand
            ok = True
            break
        if ok:
            chosen_target = t
            break
    if not chosen_target:
        continue
    orig_form = chosen_target["form"]
    corrupted_form_iast = transliterate(corrupted_slp1, Scheme.Slp1, Scheme.Iast)
    corrupted_text_iast = apply_word_swap(s["text_iast"], orig_form, corrupted_form_iast)
    if not corrupted_text_iast:
        continue
    used_sent_idx.add(si)
    typo_cases.append({
        "category": "multi_letter_typo", "gap_bucket": "multi_letter_typo",
        "sentence_index": si, "folder": s["folder"], "file": s["file"],
        "sent_id": s["sent_id"], "original_text_iast": s["text_iast"],
        "corrupted_text_iast": corrupted_text_iast,
        "target_word_original": orig_form, "target_word_corrupted": corrupted_form_iast,
        "edit_distance": levenshtein(to_slp1(orig_form), corrupted_slp1),
        "note": f"'{orig_form}' -> '{corrupted_form_iast}' (edit distance "
                f"{levenshtein(to_slp1(orig_form), corrupted_slp1)}); the engine's spelling "
                f"corrector only tries single-edit candidates, so a 2+-edit typo is expected "
                f"to be left unrecognised at review severity rather than asserted as an error.",
    })

print(f"multi-letter typo corruptions: {len(typo_cases)}  (construction attempts: {attempts})")

all_cases = karaka_cases + subject_cases + typo_cases
for c in all_cases:
    c["corrupted_text_deva"] = transliterate(c["corrupted_text_iast"], Scheme.Iast, Scheme.Devanagari)
    c["original_text_deva"] = transliterate(c["original_text_iast"], Scheme.Iast, Scheme.Devanagari)
    c["expected_flagged_surface_deva"] = transliterate(c["target_word_corrupted"], Scheme.Iast, Scheme.Devanagari)

print(f"\nTOTAL Experiment-2 corrupted cases: {len(all_cases)}")
print(f"  karaka-role (dhatu-triggered non-Sasthi): {len(karaka_cases)}")
print(f"  karaka-role (subject-case): {len(subject_cases)}")
print(f"  multi-letter typo: {len(typo_cases)}")

(HERE / "exp2_corruptions.json").write_text(
    json.dumps(all_cases, ensure_ascii=False, indent=1), encoding="utf-8"
)
print("wrote exp2_corruptions.json")
