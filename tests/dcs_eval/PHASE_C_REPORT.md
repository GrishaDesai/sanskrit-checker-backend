# Phase C Report — syntax layer: subject-finder, liṅga agreement, kāraka extension

Measured against both sets on every change, per Phase D.

## Step 0 — the 16 → 28 gender-agreement shift is a unit mismatch, not a regression

Both engines were run over the same 260 sentences from an isolated copy of the
pre-Phase-A code (`scripts` unchanged, baseline `app/` restored from the
backup + `git show HEAD`). The syntax-layer counts come out **identical**:

| | pre-Phase-A baseline | post-Phase-A |
|---|---|---|
| `syntax:gender` flags | 20 | **20** |
| `syntax:subject_verb` flags | 8 | **8** |
| `agreement_error` flags, total | 28 | **28** |
| sentences where gender is the *only* FP mechanism | **16** | 17 |
| `token:invalid` flags | 26 | 16 |

The original Phase 1 report's "16 / 65" counted **FP sentences by sole
mechanism**; the "28" in the Phase A+B report counted **flags** (20 gender +
8 subject-verb). Same data, two units. Nothing in A2 or A4 touched the syntax
layer — they only changed `token:invalid`.

The one genuine movement is **+1 sentence**: a sentence that previously had
both a spelling FP and a gender FP now has only the gender FP, because A4
cleaned the spelling flag. That is the visibility effect, and its size is 1.

## Step 1 — एक sarvādi defect: prepared, not filed

`gh` is not installed and no GitHub credentials are available in this
environment, so the issue could not be filed. A complete, self-contained
issue — reproduction script, full masculine and feminine paradigm tables, the
25-stem audit, the kosha lookups, and a suggested fix — is at
[`docs/vidyut-issue-eka-sarvadi.md`](../../docs/vidyut-issue-eka-sarvadi.md),
ready to paste at https://github.com/ambuda-org/vidyut/issues/new.

## Step 2 — subject-finder

Avyayas are now excluded from subject candidacy via the same vidyut
`is_avyaya` flag Phase A introduced, and the finder *skips* rather than
*abandons*, so a real subject sitting after a particle is still found.

**For the record — were the 7 particle/relative-pronoun misfires already
resolved incidentally by A4?** No. A4 gated the spelling path only; the
subject-verb flag count was 8 both before and after Phase A. Step 2 resolved
2 of them directly (`Subject 'हि'`, `Subject 'तथा'`).

Two further defects were found and fixed while measuring:

- **Subject vacana was read from the wrong case.** `_entry_vacana` ranked over
  readings in *every* vibhakti, so नरा was assigned the vacana of its
  Tṛtīyā-singular homograph. Now read from the Prathamā reading.
- **The `-ए` syncretism.** For an a-stem, `-e` is Saptamī *singular* and
  Prathamā/Dvitīyā *dual* simultaneously, so locatives (स्थिते, युद्धे,
  निरोधे, सर्वात्मके) were being read as nominative duals and then reported as
  number mismatches. The check now requires the vacana to be *determined* —
  all top-rank readings agreeing on number — which demotes these to review
  while leaving बालकाः / बालकौ (Prathamā/Dvitīyā syncretism, same vacana
  either way) at error tier.

## Step 3 — liṅga-agreement gating

Four gates, each added because a measurement demanded it:

1. **Neither token may be an avyaya.** वा and केवलम् carry unrelated
   declinable homographs; this is why `'वा' (Pum) does not agree with
   'चूर्णं'` was ever emitted. Extended to **अव्ययकृत्** — a कृदन्त in
   क्त्वा / ल्यप् / तुमुन् is indeclinable (क्त्वातोसुन्कसुनः १.१.४०,
   कृन्मेजन्तः १.१.३९), read from vidyut's own `krt` field on the Krdanta
   entry, which is what वारयित्वा needed.
2. **No pairing across a clause boundary.** इति closes the clause it follows
   and is routinely written fused to the next word, so the marker is matched
   at the start of a token (इत्यर्थः), not only as a standalone token.
3. **Shared vacana.** विशेषण and विशेष्य are समानाधिकरण — they agree in
   liṅga, vacana and vibhakti together. Both readings are Prathamā by
   construction here, so vacana is the part left to check; मृदा/लिप्तं and
   भावा/व्याख्याताः were never in apposition.
4. **Ambiguous analysis → review tier**, not suppression, per the brief.

**Ambiguity had to be measured per grammatical category, not globally.** A
first version demoted on any ambiguity and lost two gold cases: बालकाः has
top-rank Prathamā readings split Pum/Stri but agreeing on Bahu, and verb
agreement does not depend on liṅga. So the liṅga check is blocked by liṅga-or-
vacana ambiguity, and the verb check by vacana ambiguity only.

**Ranking is load-bearing.** Counting raw Kosha entries instead of top-rank
ones calls वृक्षः ambiguous (30 readings) and loses a genuine gold gender
error, whereas at top rank वृक्षः is unambiguously Pum/Eka and या really is
Pum-or-Stri.

## Step 4 — kāraka extension, and where it actually stops

The three duplicated `is_sasthi` blocks are now one case-general check, gated
by `_sole_argument_candidate`, which asserts nothing unless: exactly one
finite verb (single clause), every pre-verb word analysed, and exactly one
non-Prathamā nominal. Multi-nominal and cross-clause cases return `None` by
construction, not by omission.

**A measured correction to the plan.** Generalising the *verb*-governed check
to all cases immediately produced a gold-set false positive:

> `बालकः कक्षायां पठति।` — "the boy reads in the classroom" — flagged, because
> कक्षायाम् was the sole non-Prathamā nominal and पठ् governs Dvitīyā.

This is the real boundary, and it is not a tuning problem. Tṛtīyā can be
करण, Saptamī अधिकरण, Pañcamī अपादान — all independent kāraka roles that
coexist with the कर्म. Deciding whether such a nominal fills the कर्म slot or
an adjunct slot is exactly the binding information morphology does not carry.
षष्ठी is the principled exception: शेषे षष्ठी (२.३.५०) defines it as the
non-kāraka remainder, so a genitive in an argument slot is confirmable. The
verb-governed check is therefore restricted to cases that cannot be a kāraka
in their own right — which, on Pāṇini's own definition, is षष्ठी.

**Where the extension is sound: upapada.** An upapada fixes the vibhakti of
the word *immediately beside it* outright — नमः takes चतुर्थी (२.३.२८), सह
takes तृतीया (२.३.१९) — leaving no competing kāraka slot. Here any case other
than the governed one is confirmable, and this is what delivers the
instrumental and dative extension the phase asked for.

Result: `upapada_wrong_noncase` recall **0/5 → 2/5 (40%)**.

## Step 5 — standard numbers

| metric | Phase A+B | **after Phase C** |
|---|---|---|
| Unrecognized-token rate | 30.6% | **30.6%** (unchanged — Phase C is syntax-only) |
| **DCS false-positive rate** | 16.2% | **8.5%** (22/260) |
| — token-level error flags | 16 | **16** |
| — syntax-level error flags | 26 | **6** |
| Review-only rate | 75.0% | **81.2%** ⚠ |
| Fully clean | 8.8% | 10.4% |
| Gold FP-avoidance | 43/43 | **43/43** |
| Gold review-correctness | 34/34 | **34/34** |
| Gold error recall | 38/57 (66.7%) | **38/57 (66.7%)** |
| Exp-2 kāraka recall | 0.9% | **1.9%** (2/106) |
| — upapada_wrong_noncase | 0/5 | **2/5 (40%)** |
| Exp-2 multi-letter typo | 12/100 | 12/100 |

**Review-tier rate is up to 81.2%, and it is flagged as required.** 6.2 points
of the rise are deliberate: findings that were previously asserted as errors
on ambiguous evidence are now offered instead of dropped. This is the intended
direction for trust, but it is now the largest single product-quality concern:
four sentences in five carry at least one advisory. Roughly 30.6% of tokens
are still unrecognized, and that — not the syntax layer — is what feeds it.

### Resolution of the 28 gender-agreement + 2 kāraka FPs

| | before | error tier | demoted to review | suppressed |
|---|---|---|---|---|
| gender-agreement | 20 | **2** | 9 | 9 |
| subject-verb | 8 | **4** | 5 | — |
| kāraka | 2 | **0** | — | 2 |

Subject-verb totals 9 rather than 8 because the finder, no longer stopping at
an avyaya, reaches a different candidate in some sentences; the extra findings
are review-tier.

**The 6 remaining error-tier syntax FPs, by cause:**

- `दण्डः/शुल्कं`, `गलः/पृष्ठं` (2, gender) — **coordinate enumerations**. Both
  members are genuinely Prathamā/Eka and genuinely differ in liṅga; they are
  list items, not विशेषण–विशेष्य. Separating a list from apposition needs
  coordination structure. **Category 2, out of scope.**
- `उन्मत्तो/मन्यन्ते`, `स्नातानुलिप्तं/भजन्ते` (2, subject-verb) — the real
  subject **follows** the verb (इतरे जनाः, नीलमक्षिकाः); the flagged word is a
  fronted object or inside a quoted clause. **Category 2, out of scope.**
- `नरा/पश्यन्ति` (1) — corpus orthography: the text writes नरा for नराः, and
  the Kosha's only top-rank reading is Prathamā *singular*.
- `प्रधानं/भावः` (1) — भावः is a noun that VerbGrammar's index also matches as
  a tiṅanta (reported as "Uttama Dvi", plainly spurious). A verb/noun
  homograph problem, not an agreement one.

## The highest-value next item, measured

Investigating why the 80-case `subject_wrong_case_instrumental` bucket stays
at 0% produced a finding that **revises a Phase A conclusion**:

| cause | n |
|---|---|
| no finite verb recognised — genuinely verbless nominal sentence | 40 |
| no finite verb recognised — **but the Kosha does see a tiṅanta VerbGrammar missed** | ≤29 |
| another nominative remains, so the corrupted sentence is still grammatical | 10 |
| multi-clause | 1 |

The middle row is the actionable one. `verb_readings` — the only thing the
syntax layer uses to find a verb at all — comes solely from VerbGrammar, which
indexes **लट्-कर्तरि only**. Sentences whose verb is उच्यते (कर्मणि), चकार
(लिट्), स्यात् (विधिलिङ्) or आख्यायते have *no verb* as far as every syntax
check is concerned.

Phase A measured that extending VerbGrammar to all ten lakāras × kartari/
karmani recovers **0** additional *recognized tokens*, because the Kosha
already covers those forms for validity — and concluded, correctly for that
purpose, not to build it. That conclusion does not carry over here: the same
extension is worth little for recognition and potentially a great deal for
**syntax**, which reads a different field. Recommended as the next piece of
work, with its own measurement cycle — it changes the `has_action_verb` gate
that controls the entire liṅga-agreement section, so it carries real
false-positive risk and should not be bolted on at the end of this phase.

The remaining 10 + 40 cases are genuinely out of reach: a corrupted nominative
in a sentence that still has another nominative is **category 3** (valid
Sanskrit, different meaning), and a verbless nominal sentence has no argument
structure for any kāraka check to consult.

## Incidental fix

Mapping a syntax issue back onto its token was gated on `tok.status ==
"valid"`. Sandhi runs first and marks the *first* word of a junction — often
the same word an agreement issue lands on — so a review-tier style suggestion
silently hid a confirmed error from `error_count` and `syntax_error_count`
(`सुन्दरः बालिका अस्ति।` reported `syntax_error_count=0` while carrying an
error-severity liṅga issue). An error-severity issue now outranks a
review-tier flag on the same token. Both eval harnesses read `syntax_issues`
directly, so no measurement in this report is affected.

## Note on measurement definitions

`SyntaxIssue` now carries a `severity`, mirroring `TokenResult`. All three
harnesses (`evaluate_gold.py`, `run_exp1.py`, `run_exp2.py`) were updated to
count only **error-severity** syntax issues as defects, exactly as they
already did for token flags. Before Phase C every syntax issue was error by
construction, so this changes no historical number — but the FP rates above
and those in earlier reports are only comparable because of that.
