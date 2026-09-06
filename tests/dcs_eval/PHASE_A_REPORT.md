# Phase A + B Report — recognition layer and the spelling-assertion root cause

Measured against both sets on every change, per Phase D. Baselines in this
document were re-measured live from the code as it stood before this work,
not taken from the brief — two of them differed (see §1).

## 1. Corrected baselines

| metric | brief | measured baseline | after Phase A+B |
|---|---|---|---|
| Unrecognized-token rate (DCS 260) | 31.4% | 31.4% (508/1617) | **30.6%** (495/1617) |
| False-positive rate (DCS 260) | 25% | **20.0%** (52/260) | **16.2%** (42/260) |
| — of which token-level (`invalid`) flags | — | 26 | **13** |
| — of which syntax flags (Phase C's problem) | — | 30 | 30 |
| Review-only rate | ~66–72% | 71.9% | 75.0% |
| Fully clean | — | 8.1% | 8.8% |
| Gold FP-avoidance | 43/43 | 43/43 | **43/43** |
| Gold review-correctness | 34/34 | 34/34 | **34/34** |
| Gold error recall | 66.7% (38/57) | **64.9% (37/57)** | **66.7% (38/57)** |
| संस्क्रुतम् caught | (regressed) | **no** | **yes** |
| Exp-2 recall, kāraka | 0.9% | 0.9% (1/106) | 0.9% (1/106) |
| Exp-2 recall, multi-letter typo | 15.0% | 15.0% | 12.0% |

Two baseline corrections matter:

- **The rejected 4+char consonant-deletion guard was never actually reverted.**
  It was still live in `_find_spelling_correction`. It is what moved the DCS FP
  rate from the brief's 25% to the measured 20% — by relocating noise from
  error tier to review tier, exactly as the brief suspected — and what cost the
  संस्क्रुतम् catch (37/57, not 38/57). Phase B was therefore live work.
- **The 12.0% multi-letter-typo recall is not a quality signal.** All 12 catches
  propose the *wrong* correction (गृहीत्क → गृहीत, not गृहीत्वा; भूगनाम् →
  भूघनाम्, not भूतानाम्; …). 0/12 are right. The baseline's 15 were the same
  phenomenon. Recall in this bucket measures how often a 2-edit corruption
  drifts within one edit of some unrelated real word, not detection.

## 2. A1 — premise falsified, no code written

Chedaka's `data=None` is its **unknown** marker, not a lexicon hit: the nonsense
string `kqzXw` returns exactly the same shape as परिणामलक्षणा (one token,
`data=None`, `lemma=None`). Chedaka does not know परिणामलक्षणा.

Across all 508 unrecognized tokens, the count of "Chedaka recognises it as one
word but `_raw_check` does not" is **0**. There was nothing to integrate.

The data-quality check A1 asked for has its answer: **no cheda-vs-Kosha validity
disagreement exists in the direction that would help.** Disagreement runs the
other way only (the engine recognises forms Chedaka's segmenter cannot analyse),
which is not actionable for recognition.

## 3. A2 — done, and the audit found a much larger sibling

The normalization ladder was five copy-pasted blocks in `_raw_check` plus a
sixth, *drifted* copy in `_raw_kosha_entries` (the supplemental lexicon was
consulted for some endings and not others). Both now walk one table,
`PADANTA_FINAL_VARIANTS`.

Added, per the brief: the जश्त्व family (८.२.३९ झलां जशोऽन्ते) — `d→t` and its
siblings `b→p`, `g→k`, `q→w`, `j→c`. उपरिष्टाद् now resolves like उपरिष्टात्.
Worth 12 occurrences (0.7% of tokens); small, as predicted.

**The audit for "other missing pairs in the same family" found a bigger one**:
यण् (६.१.७७ इको यणचि). A pada-final इ/उ/ऋ becomes य्/व्/र् before a vowel, and
when the edition prints the words spaced, the यण्-final fragment arrives as its
own token: इत्य्, ह्य्, भवत्य्, यद्य्, तान्य्, करणान्य्, एतास्व्. These were
systematically unrecognized *and* systematically mis-"corrected" (इत्य् → इत्).
Nine of the 24 token-level FPs at that point were this single pattern. Rows
`y→i/I`, `v→u/U`, `r→f/F` fixed it: DCS FP 18.8% → 15.4% in one change, gold
unchanged.

## 4. A3 — premise falsified, no code written

Two independent measurements:

1. **Deriving subanta paradigms via `Vyakarana()` from Kosha-attested stems and
   matching against the unrecognized forms recovers 0 / 508.** The Kosha is
   already a complete paradigm expansion of its own stem list, so re-deriving
   from those same stems is redundant by construction. This is the structural
   difference from VerbGrammar, which genuinely added Dhātupāṭha roots the Kosha
   lacked.
2. **एकस्मिन् is not a missing-table problem — it is an upstream vidyut defect.**
   `Vyakarana().derive()` itself yields एके / एकाय / एकस्य: vidyut declines एक
   as a plain *a*-stem and omits it from its सर्वादि gaṇa. Audited all 25
   सर्वादि stems — sarva, viśva, ubha, ubhaya, katara, katama, anya, anyatara,
   itara, tva, nema, sama, sima, pūrva, para, avara, dakṣiṇa, uttara, apara,
   adhara, sva, antara all correctly produce `-smin`. **Only `eka` is
   defective**, in both the Kosha (एकस्मिन्/एकस्मै/एकस्मात्/एकस्याम्/एकयोः all
   absent) and prakriya. This is a genuine Vidyut ceiling, not a strategy gap,
   and is worth reporting upstream to ambuda-org/vidyut.

The adjacent symmetric extension was also measured and rejected on evidence:
extending VerbGrammar to all 10 lakāras × Kartari/Karmani (388,174 surface
forms, 12.5s build) recovers **0 / 508 additional** — every non-लट् tiṅanta in
real prose was already in the Kosha. Adding upasarga-stripping recovers 3 forms
/ 5 occurrences (1.0%): परिमुच्यते, परिक्षरति, परिवर्जयेत्. Not built; the cost
is a 12s startup penalty for 1%.

## 5. A4 — reframed as the root-cause fix, and its acceptance criteria

The brief's governing principle — *never assert an error from absence of
evidence* — is not a veto bolted onto the spelling path; it is the spelling
path's contract. `unrecognized + exactly one 1-edit candidate ⇒ error tier`
asserts a defect from absence. The fix asserts only when absence is
**informative**: `_is_productively_composite()` decides that, and gates *both*
correction paths (the general 1-edit search and `ORTHOGRAPHIC_SUBSTITUTIONS`,
which previously bypassed every guard — it was still "correcting" शनैर् →
शणैर्).

Nothing is rewritten: the token stream is untouched and the pieces are never
substituted downstream, per the brief's constraint.

### Criteria, and what each one is holding up

Every criterion below was added because a measurement demanded it, and each was
verified against both sets:

1. **Chedaka segments into 2+ pieces it all recognises.** Splitting against a
   list of bare stems was tried first and is **vacuous**: with ~169k Kosha
   stems it "decomposes" गुरुः as guru+H, पठति as paWa+ti and रामः as rAma+H,
   which would veto everything. Not used.
2. **Sandhi visibly applied at the junction** — the surface is not the plain
   concatenation of the pieces. Without this, रामेन (रा+मेन) and विधालयः
   (विध+आलयः) qualify, and both are genuine typos.
   - *Refinement forced by measurement*: Chedaka reports a pada in its
     underlying -s/-r form, so विशेषः+तस्य → विशेषस्तस्य *looks* like plain
     concatenation. A non-final piece still ending in -s/-r is therefore also
     counted as sandhi evidence, since standing alone it would be written -ः.
3. **At least one piece is an अव्यय or pronoun.** This is what separates a fused
   pada pair from a compound, and it is doing the most work of the three.
   External sandhi is printed joined mainly around clitics and pronouns (तथापि,
   यश्च, मध्यतस्तु, विशेषस्तस्य); two *content* words written together are a
   समास — a single word in its own right, so its absence stays informative.
   Adding this recovered विधालयः, आशिर्वादः **and** raised gold error recall to
   38/57.
   - The अव्यय inventory is **vidyut's own** `is_avyaya` flag on the Kosha
     prātipadika, not a curated list. Chedaka's copy of that flag is unusable
     here (it reports `ca` and `atra` as non-avyaya), so the Kosha is read
     directly. Pronouns come from PRONOUN_MAP plus the सर्वादि stem set, since
     PRONOUN_MAP holds only ~21 surface forms and misses obliques like तस्य.

### Required negative test (the brief's CRITICAL item)

| token | note | composite | outcome |
|---|---|---|---|
| चेन्न | valid Sanskrit (चेत्+न) | True | review — correct |
| अहेतुमन् | Chedaka junk split अह+इत्+उम्+अन् | True | review — acceptable (अहेतुमत् is a real word; nothing suppressed) |
| उपरिष्टाद् | was the up+arizwAd junk split | False | now **valid** via A2 |
| संस्क्रुतम् | genuine typo | False | **error** ✓ |
| सन्स्कृतम् | genuine typo | False | **error** ✓ |
| विधालयः | genuine typo | False | **error** ✓ |
| आशिर्वादः | genuine typo | False | **error** ✓ |
| रामेन | genuine typo | False | **error** ✓ |
| तथापि / यश्च | valid fusions | True | review — correct |

**Residual risk, stated rather than papered over**: अहेतुमन् is vetoed via the
junk piece `अह`, which the Kosha does flag as an अव्यय. The veto fired for the
wrong reason and happened to reach the right tier. A genuine typo that both
(a) segments with a real particle and (b) shows sandhi at the junction would be
demoted to review. None was found in either set, but the mechanism exists.

## 6. A nasal-variant guard, added on evidence

Four of the 26 token-level FPs were "corrections" between equally correct
spellings — असंप्रज्ञातो → असम्प्रज्ञातो, शंकरे → संकरे. अनुस्वारस्य ययि
परसवर्णः (८.४.५८) makes the homorganic nasal a *substitute* for anusvāra, so
both spellings are correct and choosing between them is house style.

The sūtra's ययि condition is enforced, not waved at, and it is load-bearing:
यय् excludes the sibilants and ह, so before a sibilant anusvāra has no
parasavarṇa substitute — which is why संस्कृतम् is right and सन्स्कृतम् is a
**genuine error**. A first, unconditioned version of this guard lost both
सन्स्कृतम् gold cases; adding the ययि condition and a homorganicity check
recovered them.

## 7. Phase B — the rejected guard

Removed. `grep` over `app/` finds no trace in any source file (the only matches
are inside vidyut's binary corpus files). A4's evidence test subsumes its
intended function without reintroducing what it was papering over: the guard's
crude proxy was *word length*, which is why it also silenced संस्क्रुतम्; the
replacement tests *decomposability into a fused pada pair*, which संस्क्रुतम्
fails and तथापि passes.

## 8. What is left, and where it belongs

Of the 42 remaining FP sentences, **30 of the 43 flags are syntax issues** —
28 gender-agreement, 2 kāraka. Token-level FPs are down from 26 to 13. **The
remaining FP mass is Phase C's, not Phase A's.**

The 13 residual token FPs are: 2 Chedaka mis-analyses (संहतास्तु split as
संहत+अस्तु rather than संहताः+तु; अत्रैवं gets no analysis at all), 1 the एक
gap above, and 10 genuine Kosha lexicon gaps (सूर्प, अहेदं, आहितकं, उञः,
नक्षत्राख्यां, अपराह्णिकं, रक्तास्रावः, …) where the engine finds one unrelated
word an edit away.

The unrecognized-token rate barely moved (31.4% → 30.6%) and that is the honest
result: **~49% of it is long compounds Chedaka cannot segment, ~48% is
sandhi-fusion, and neither is a missing-paradigm problem**. Naive stem-chain
decomposition "solves" 144 of 259 compounds but produces वानूपजलजा = वा+नू+प+जलजा
and भावाभावसंवेदनाद् = भा+वा+भाव+संवेदनाद्, so it is not usable as evidence.
Reliable compound-member segmentation is the boundary of what vidyut provides
here. What *did* move is the number that matters for trust: the rate at which
that unrecognized mass is converted into a confident false accusation.
