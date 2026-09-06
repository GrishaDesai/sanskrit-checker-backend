# DCS Independent Evaluation — Phase 1 Report

Evaluation-only. No file under `app/*.py` was modified during this work. All
scripts, intermediate pools, and full engine output are checked in alongside
this report under `tests/dcs_eval/` for audit.

## 1. What was read first

`app/main.py`, `app/sanskrit_engine.py`, `app/karaka_syntax.py`,
`scripts/evaluate_gold.py`, `scripts/build_gold_dataset.py`. Key facts that
shaped the design below:

- `SanskritEngine.check_text(text)` returns tokens with `.status`/`.severity`
  ("error" vs "review") and a `.syntax_issues` list. `evaluate_gold.py`'s
  `engine_verdict()` treats a sentence as flagged iff **any token has
  `severity == "error"` OR there is at least one `syntax_issue`** — review-tier
  findings (unrecognised words with no confident fix, unapplied sandhi) never
  count. This exact rule was reused for both experiments below.
- `karaka_syntax.py`'s kāraka checks are narrow by construction: the
  transitive-verb-object check (`TRANSITIVE_DHATU_MAP`), the Caturthī/Pañcamī
  dhātu checks, and the upapada-vibhakti check **all gate on
  `is_sasthi`** — i.e. they only catch an object/argument that is wrongly in
  Ṣaṣṭhī (genitive). A wrong case that isn't Ṣaṣṭhī (Instrumental, Accusative,
  etc.) is never tested at all. Separately, the subject-verb agreement
  check's subject-finder only recognises a subject via a pronoun match, a
  genuine Prathama-vibhakti nominal reading, or a small set of surface-ending
  heuristics (`AH`, `as`, `aH`, `o`, `An`) — a noun in any oblique case is
  simply never considered as a subject candidate, so a subject-case error
  produces **no check at all**, not a missed check.
- `check_word()`'s spelling repair (`_find_spelling_correction`) only tries
  **single**-edit candidates (`_edit_distance_1_candidates`: one deletion,
  one phonetically-constrained substitution, one insertion, one adjacent
  transposition). An unrecognised word with no 1-edit fix is left at
  `severity == "review"`, i.e. **not counted as a flag** — a designed
  precision-over-recall choice, but it means any 2+-edit typo is
  architecturally invisible to the "error" tier unless it coincidentally
  lands within one edit of some other real word.

These three points are exactly the two "known gaps" named in the brief, and
they were used to design Experiment 2's corruptions.

## 2. DCS access method

Unauthenticated GitHub REST API (`api.github.com`) was used for directory
listing (60 req/hour is enough — only ~3 calls were needed by getting the
**entire** `dcs/data/conllu/files` subtree in one recursive
`git/trees/<sha>?recursive=1` call, keyed off the tree SHA found in the parent
directory's listing: 23,550 entries, not truncated). Actual file content was
pulled from `raw.githubusercontent.com` (not rate-limited the same way),
percent-encoding each path segment. **A true `git sparse-checkout` clone was
attempted first and abandoned**: DCS folder/file names are long and contain
commas/diacritics (e.g. `Commentary on the Kāvyālaṃkāravṛtti-0000-...,
Prathama adhyāyaḥ, 1-2335.conllu`), which blew past Windows' path-length
limit during checkout (`Filename too long`) — the GitHub-API route sidesteps
this entirely since nothing is written to disk under the original long names.

226 files (max 10 per whitelisted folder, 400–60,000 bytes, `*_parsed`
variants skipped) were fetched, yielding a pool of **4,090 sentences** with
full per-token CoNLL-U data. All fetch scripts are in this directory
(`filter_tree.py`, `fetch_pool_rich.py`) and are safely re-runnable.

## 3. The sandhi-split finding (read this before trusting Experiment 1)

DCS is a "sandhi-split corpus" in a specific, narrower sense than the phrase
might suggest, and it matters for how "unmodified" the input really is:

- Each sentence carries a `# text = ...` comment line holding the **actual,
  continuous, un-split surface text exactly as printed in the source
  edition** — sandhi fully applied, no spaces inserted at word junctions the
  original didn't have. This is what a real reader encounters and what a
  human would type.
- The **per-token analysis rows below that line are what is sandhi-split**:
  each word/compound-member is decomposed into its own row with a
  linguistically reconstructed pre-sandhi citation form in an `Unsandhied=`
  MISC field, which frequently **differs from the attested `FORM`**
  (verified directly, e.g. attested `yogo` vs. reconstructed `yogaḥ`;
  attested `tābhir` vs. reconstructed `tābhiḥ`; attested `daṇḍanītiśceti` —
  one written word — spanning three reconstructed components
  `daṇḍanītiḥ`, `ca`, `iti`). Multi-word external-sandhi fusions and
  compound-internal members are both represented the same way, as a
  covering `N-M` range row over several leaf rows.

**Decision made**: Experiment 1 and the base sentences for Experiment 2 both
use the `# text = ...` line, transliterated IAST→Devanagari via
`vidyut.lipi`, i.e. the real continuous surface text, not the split
analysis. This is the right choice for "unmodified natural input" — but it
also means the test sentences **legitimately contain word-fused sandhi with
no space**, which the checker's own tokenizer (splitting on Devanagari-letter
runs) treats as a single token. This turned out to be the single largest
source of false positives in Experiment 1 (see section 4) and is flagged
prominently there rather than quietly smoothed over.

A leaf token was only used as an Experiment-2 corruption target when (a) its
ID was not covered by any `N-M` range (guaranteeing it occupies its own
whitespace slot in `# text`, so it can be safely located and replaced) and
(b) `FORM == Unsandhied` (guaranteeing no cross-word sandhi already altered
its ending, so a case-swap produces a clean, unambiguous result).

## 4. Genre classification (prose whitelist)

271 top-level folders exist in `dcs/data/conllu/files` (full list in
`folder_names.txt`). No genre field exists; classification is by title
identity, per the brief's rules:

**Hard-excluded as Vedic/verse**: all 4 Vedic Saṃhitās under any name
(Ṛgveda incl. Khilāni/Vedāṅgajyotiṣa/Vidhāna; both Atharvaveda recensions +
Prāyaścittāni/Pariśiṣṭa; Vājasaneyisaṃhitā, Taittirīyasaṃhitā, Kāṭhakasaṃhitā,
Maitrāyaṇīsaṃhitā as Yajurveda recensions), all Brāhmaṇas, Āraṇyakas
(extended beyond the brief's literal list, as archaic Vedic-register
prose/verse attached to a specific Veda — a defensible reading of "Yajurveda
etc., all recensions"), classical mahākāvya (Kumārasaṃbhava, Meghadūta,
Kirātārjunīya, Buddhacarita, Saundarānanda), dūta/lyric/śataka verse genres
(Gītagovinda, Caurapañcaśikā, Amaruśataka, Bhallaṭaśataka, Sūryaśataka,
Śatakatraya, Haṃsadūta/saṃdeśa, Kokilasaṃdeśa, Ṛtusaṃhāra, Āryāsaptaśatī),
verse lexicons/nighaṇṭus (Amarakośa, Abhidhānacintāmaṇi, all `*nighaṇṭu`
titles, Trikāṇḍaśeṣa), and base verse-kārikā treatises (Sāṃkhyakārikā,
Spandakārikā, Mūlamadhyamakārikāḥ, Gorakṣaśataka, Abhidharmakośa,
Viṃśatikākārikā, Kāvyādarśa, Kāvyālaṃkāra — verse even though sāstric in
content).

**Skipped as mixed/ambiguous** (per the brief's explicit instruction to skip
rather than guess): all Purāṇas, Mahābhārata/Harivaṃśa, Rāmāyaṇa, Manusmṛti
and the rest of the smṛti corpus (Kātyāyana-, Nārada-, Parāśara-,
Yājñavalkya-, Viṣṇu-, Vṛddhayama-smṛti), all Śrautasūtras/Gṛhyasūtras/
Dharmasūtras (terse, Vedic-school-attached ritual prose — genuinely prose,
but a judgment call left unresolved), all Upaniṣads (principal ones are
archaic Vedic-register prose, minor ones are frequently verse — not cleanly
sortable without per-text checking), the entire rasaśāstra/alchemy cluster
(~25 titles: Rasārṇava, Rasaratnasamuccaya + its commentaries, etc. — could
not verify prose-vs-verse ratio without individual research) and the tantra
cluster (similarly unverified), Pañcatantra/Hitopadeśa/Kathāsaritsāgara and
other narrative story collections (could not isolate prose frame from
embedded verse), ornate literary prose kāvya (Daśakumāracarita, Harṣacarita
— prose, but ornate/compound-heavy literary register, not sāstric), and a
handful of single ambiguous titles (Padārthacandrikā, Sarvāṅgasundarā,
Abhinavacintāmaṇi, Saṃvitsiddhi) whose exact identity/genre I could not
confirm confidently.

**Included as classical prose** (35 folders, 2,084 `.conllu` files total):
Nyāyasūtra, Nyāyabhāṣya, Vaiśeṣikasūtra, Vaiśeṣikasūtravṛtti, Yogasūtra,
Yogasūtrabhāṣya, Tattvavaiśāradī, Pāśupatasūtra, Pañcārthabhāṣya, Śivasūtra,
Śivasūtravārtika, Mīmāṃsāsūtrabhāṣya, Sāṃkhyakārikābhāṣya,
Sāṃkhyatattvakaumudī, Prasannapadā, Nyāyabindu, Tarkasaṃgraha,
Sarvadarśanasaṃgraha, Arthaśāstra, Kāmasūtra, Kāśikāvṛtti, Mugdhāvabodhinī,
Nirukta, Kāvyālaṃkāravṛtti + its Commentary, Rājamārtaṇḍa,
Abhidharmakośabhāṣya, Viṃśatikāvṛtti, Carakasaṃhitā, Suśrutasaṃhitā,
Aṣṭāṅgahṛdayasaṃhitā, Aṣṭāṅgasaṃgraha, Indu (ad AHS), Carakatattvapradīpikā,
Spandakārikānirṇaya. Rule of thumb applied: darśana-sūtra base texts (terse
aphoristic prose, not metrical) and prose bhāṣya/vṛtti/vārtika/ṭīkā
commentaries on a clearly philosophical/sāstric (not kāvya/purāṇa/tantra)
base text, plus the brief's named examples (Arthaśāstra, Kāśikāvṛtti-style
grammatical commentary, the four major Āyurvedic saṃhitās). This whitelist
is intentionally conservative (35 of 271 folders) — the project owner should
treat the "skipped" bucket, especially the Dharmasūtra/Śrautasūtra/Gṛhyasūtra
cluster, as the first place to revisit if a larger prose sample is wanted.

## 5. Experiment 1 — false-positive stress test (unmodified engine)

**Sample**: 260 sentences, `# text` reconstructed → Devanagari, sampled from
the 35-folder prose whitelist (4–22 words, script-only, no avagraha),
deduplicated, disjoint from Experiment 2 (a separate 1,898-sentence pool was
carved off first and Experiment 2 draws only from that). Ran through
`SanskritEngine.check_text()` unmodified.

**Result**:

| | count | rate |
|---|---|---|
| **False positives** (≥1 error-severity token OR ≥1 syntax_issue) | **65 / 260** | **25.0%** |
| Review-only (no hard error, but ≥1 review-tier flag) | 174 / 260 | 66.9% |
| Fully clean (no flags of any kind) | 21 / 260 | 8.1% |

This is **dramatically different from the hand-seeded gold set's 0% FP rate
(43/43 correct sentences never flagged)**. The gap is explained, not just
asserted — breaking the 65 FPs down by mechanism:

- **38 / 65 (58%): sandhi-fusion mis-tokenization.** Real prose freely writes
  two words joined by sandhi with no space (`tathā + api → tathāpi`, written
  as one continuous graphic unit — completely normal, correct Sanskrit, not
  a typo or OCR artifact). The checker's tokenizer treats the fused unit as
  one word; it isn't in the dictionary as a unit, and the single-edit
  spelling corrector then sometimes finds *some other* unrelated real word
  one edit away and confidently "corrects" to it. Examples actually
  produced: चेन्न (cet+na) → suggested चेन; तथापि (a genuinely correct
  compound clitic) → suggested अथापि; यश्च (yaḥ+ca) → suggested यश; चैको
  (ca+ekaḥ) → suggested ऐको. **This is the single biggest, most actionable
  finding**: the gold set's own design (documented in
  `build_gold_dataset.py` section 7) always keeps words space-separated and
  tests sandhi *application* as a separate "review"-tier concern — it never
  contains a sentence where sandhi has *already* fused two words with no
  space, so this failure mode was structurally invisible to the existing
  150-case set.
- **16 / 65 (25%): gender-agreement over-triggering.** The bare-nominal-
  apposition gender check (`karaka_syntax.py` section 5) is explicitly
  designed "deliberately narrow" for simple two-word copula sentences
  (सुन्दरः बालिका), but real prose routinely has relative clauses,
  legal/technical enumerations, and predicate constructions where two
  adjacent Prathama-case nominals of different liṅga is completely
  grammatical (e.g. listing three different-gender penalty items in one
  enumerative sentence; a relative-clause pronoun matched against an
  unrelated noun). The check's "no action verb" gate does not reliably
  exclude these real sentence shapes.
- **7 / 65 (11%): person/number subject-verb agreement misfires.** The
  subject-finder's ending-heuristic fallback picks the wrong word as
  "subject" in real prose with particles, relative pronouns, or fronted
  objects before the verb (e.g. picking up a particle or a genitive plural
  adjective as if it were a nominative subject).
- **2 / 65 (3%): kāraka-error misfires**, both from a genitive-relative
  construction being misread as a Ṣaṣṭhī-marked direct object of an
  unrelated transitive verb.
- 2 cases combined more than one mechanism.

Full per-sentence detail (all 260, including every flagged token/
syntax_issue) is in `experiment1_sample.json`.

## 6. Experiment 2 — recall test via gap-targeted corruption (unmodified engine)

**Sample**: 206 corrupted sentences built from the disjoint 1,898-sentence
reserve pool (zero overlap with Experiment 1 — enforced by construction:
Experiment 1 took the first 260 of a shuffled dedup list, Experiment 2 draws
only from the remainder). Case-swap corruptions were built by **re-deriving
the wrong-case surface form via a genuine `Vyakarana().derive()` call** on
the same Kosha-recognised pratipadika/liṅga (mirroring exactly
`karaka_syntax.py`'s own `_case_form()` mechanism) rather than a hand-rolled
suffix table — an early hand-rolled-suffix version of this script was
discarded after it emitted phonologically wrong endings (e.g. `-ena` where
Pāṇini's ṇatva rule 8.4.1 requires `-eṇa` after a stem containing r/ṛ/ṣ),
which the checker then "caught" as a spurious *spelling* error rather than
the intended *kāraka* error — an instructive near-miss in test-construction
methodology, corrected before the numbers below were produced.

Categories built (majority target the two named gaps, per the brief):

| category | gap bucket | n |
|---|---|---|
| `subject_wrong_case_instrumental` (Nom subject → Ins) | karaka_role | 80 |
| `object_wrong_noncase_instrumental` (Acc object of a transitive verb → Ins, i.e. wrong but not Ṣaṣṭhī) | karaka_role | 20 |
| `upapada_wrong_noncase` (Ins/Dat argument of saha/namaḥ-class upapada → Acc) | karaka_role | 5 |
| `caturthi_wrong_noncase_accusative` (Dat argument of ruc/dā-class verb → Acc) | karaka_role | 1 |
| `multi_letter_typo` (2-edit-distance spelling corruption on a real content word) | multi_letter_typo | 100 |
| **Total** | | **206** |

Sample size is smaller than the 200-300 hoped for *per bucket*: caturthi/
pañcamī-dhātu trigger verbs (ruc, dā, krudh, kup, īrṣy, bhī, trā, pramad) and
upapada connectives (saha, namaḥ, svasti, alam...) are simply rare in
philosophical/sāstric prose compared to the everyday-narrative register the
hand-seeded set used, so only 26 dhātu/upapada-triggered cases were found
across the whole 1,898-sentence pool even after scanning all of it; the
subject-case and typo categories are not lemma-constrained and hit their
target counts easily (80 and 100 respectively, capped by design).

**Result**:

| | caught | total | recall |
|---|---|---|---|
| **Overall** | **16** | **206** | **7.8%** |
| karaka_role (all subtypes combined) | 1 | 106 | **0.9%** |
| — subject_wrong_case_instrumental | 1 | 80 | 1.2% |
| — object_wrong_noncase_instrumental | 0 | 20 | 0.0% |
| — upapada_wrong_noncase | 0 | 5 | 0.0% |
| — caturthi_wrong_noncase_accusative | 0 | 1 | 0.0% |
| multi_letter_typo | 15 | 100 | 15.0% |

**This confirms both hypothesized gaps as close to total blind spots**, far
below the existing gold set's aggregate 66.7% error recall:

- The single karaka_role "catch" is not the intended mechanism at all: it
  was the same bare-nominal gender-agreement check from section 5 misfiring
  on two adjacent nominals, not a genuine kāraka-case check. **Effectively
  0/106 (0%) via any check actually designed to catch a case-role error** —
  this matches the code reading exactly: every kāraka/upapada check in
  `karaka_syntax.py` is gated on `is_sasthi`, and the subject-agreement
  check's subject-finder never even considers an oblique-case noun, so
  there is no code path that could catch these corruptions by design, not
  by accident of coverage.
- The 15/100 (15%) typo "catches" are, on inspection of all 15, **entirely
  incidental**: the 2-edit corruption happened to land within *one* edit of
  some other unrelated real word (e.g. गृहीत्वा→गृहीत्क was "corrected" to
  गृहीत; ईश्वरः→ईस्वरम् was "corrected" to ईश्वरम्, coincidentally right;
  भूतानाम्→भूगनाम् was "corrected" to भूघनाम्, wrong). None reflect a
  multi-edit-aware repair mechanism, because none exists
  (`_edit_distance_1_candidates` is exactly one edit by construction) — the
  hit rate is a function of how often a random 2-edit string happens to
  re-approach some other dictionary word, not of typo severity or
  detectability.

Full per-sentence detail (all 206, including every corruption's before/after
form, expected flag, and actual engine output) is in
`experiment2_sample.json`.

## 7. Direct comparison to the existing 66.7% / 100% baseline

| metric | hand-seeded gold set (150 cases) | DCS independent test |
|---|---|---|
| False-positive avoidance | 100% (43/43) | **75.0%** (195/260 sentences had no error-severity flag or syntax_issue) — a **25-point drop** |
| Error recall, overall | 66.7% (38/57) | not directly comparable — Experiment 2 was deliberately built to stress only the two *named gap categories*, not a representative mix of all error types |
| Error recall, gap-targeted categories | not previously measured (these categories were largely absent from the 150-case set, which the brief itself asked us to go beyond) | **7.8%** (16/206), with karaka-role recall at **0.9%** and multi-letter-typo recall at **15.0%**, the latter incidental rather than by design |

**This differs meaningfully from the existing numbers, in both directions of
concern the project owner asked about**:

1. The **0% false-positive rate is not representative of real running
   prose**. On natural, un-simplified classical Sanskrit sentences (not
   hand-written textbook sentences that keep every word space-separated),
   roughly 1 in 4 sentences gets at least one spurious hard-error flag,
   mostly from sandhi-fused word pairs the tokenizer cannot see as two
   words.
2. The two specifically-named recall gaps (kāraka-role errors beyond simple
   Ṣaṣṭhī-for-Dvitīyā, and multi-letter typos) are **not partially covered —
   they are essentially unimplemented**, at 0.9% and a non-representative
   15% respectively. The 66.7% aggregate recall figure from the hand-seeded
   set is being carried almost entirely by the categories it deliberately
   tests well (single-word case swaps into Ṣaṣṭhī, person/number verb
   agreement) and says very little about these two gap categories.

## 8. Constraints honored

No file under `app/` was edited. `SanskritEngine._is_recognized()` and
`SanskritEngine._raw_kosha_entries()` were called read-only from the test
scripts purely to (a) validate that a typo candidate is not itself
accidentally a real word before using it, and (b) obtain the correct Kosha
pratipadika/liṅga for genuine Paninian re-derivation of a wrong-case form —
no engine behavior was altered. The two experiments' sentence samples are
disjoint by construction (Experiment 2 only ever draws from the pool
Experiment 1 did not consume). The two headline numbers (25.0% FP rate,
7.8% gap-targeted recall) are reported separately throughout and are not
averaged or blended with each other or with the original 66.7%/100% figures.

## 9. Files in this directory

- `folder_names.txt` — all 271 DCS top-level folder names (raw listing).
- `included_files_index.json` — the 35-folder whitelist with every
  `.conllu` file path + size found for each (2,084 files).
- `filter_tree.py`, `fetch_pool_rich.py` — corpus acquisition scripts.
- `sentence_pool_rich.json` — the full 4,090-sentence pool with per-token
  CoNLL-U data, before any experiment-specific filtering.
- `build_exp1.py` → `exp1_candidates.json` (Experiment 1 input) +
  `exp2_pool.json` (the disjoint 1,898-sentence reserve for Experiment 2).
- `run_exp1.py` → **`experiment1_sample.json`** (required deliverable).
- `build_exp2.py` → `exp2_corruptions.json` (corruptions + ground truth).
- `run_exp2.py` → **`experiment2_sample.json`** (required deliverable).
