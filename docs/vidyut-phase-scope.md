# Sanskrit Proof Checker — Vidyut phase: what it catches, what it doesn't, and why

**Status: Vidyut phase CLOSED, 2026-09-06.** Closed after a final improvement
round (Part A below), a harness audit (Part B), and a full regression pass over
all 171 gold cases and all 260 DCS sentences with no live regression.

This document is the single place to find what the Vidyut-only checker
achieves and where its real boundary lies. §4 is the **gap catalogue**: every
remaining gap as its own named entry, with what triggers it, why Vidyut alone
cannot close it, and what would actually be needed. That catalogue is the
scoped starting point for the next phase.

Every number here comes from two independent evaluation sets:

- **Gold set** — 171 hand-seeded cases (`tests/gold/dataset.json`), 155 in
  scope, on clean space-separated textbook Sanskrit. Grew from 150 as the
  defect rounds in the appendix exposed untested patterns.
- **DCS sets** — 260 unmodified classical prose sentences (Experiment 1,
  false-positive stress) and 206 gap-targeted corruptions (Experiment 2,
  recall), drawn from a 35-folder prose whitelist of the Digital Corpus of
  Sanskrit. These are real running text with sandhi applied and compounds
  intact, and they are what keeps the gold set honest — the gold set alone
  reported a 0% false-positive rate where real prose showed 25%.

---

## 1. Final closing numbers (2026-09-06)

| metric | value |
|---|---|
| **Gold — false-positive avoidance** | **56/56 (100%)** |
| **Gold — review tier not mis-asserted** | **39/39 (100%)** |
| — of which actually raised an advisory | 19; **20 were silent** (see §4.9) |
| **Gold — error recall** | **44/60 (73.3%)** |
| Gold — overall in-scope pass rate | 139/155 (89.7%) |
| Gold — known-gap pass rate | 15/16 (informational only) |
| **DCS — false-positive rate** | **6.5%** (17/260 sentences) |
| — token-level error flags | 14 |
| — syntax-level error findings | 3 |
| — syntax-level review findings | 7 |
| **DCS — review-only rate** | **81.9%** |
| DCS — fully clean | 11.5% |
| **Unrecognized-token rate** | **30.4%** (491/1617) |
| Exp-2 — kāraka recall | 1.9% (2/106) |
| — upapada wrong-case | 40% (2/5) |
| — subject wrong-case | 0% (0/80) |
| — object wrong non-genitive case | 0% (0/20) |
| Exp-2 — multi-letter typo recall | 13% (13/100) — see caveat in §7 |
| Engine + API cold start | ~1.1 s |

Movement across the whole phase: DCS false positives **25% → 6.5%**, gold
error recall **64.9% → 73.3%**, with false-positive avoidance at 100%
throughout.

**Unrecognized-token attribution** (all figures from the corrected diagnostic,
see §6.2):

| cause | share of unrecognized | share of all tokens |
|---|---|---|
| Chedaka returns no analysis at all | 48.9% (240) | 14.8% |
| Chedaka splits into 2+ known pieces (A4 veto) | 48.9% (240) | 14.8% |
| pada-final voiced stop, already normalized | 2.2% (11) | 0.7% |

---
## 2. What the checker reliably catches — 🔴 confirmed tier

Every flag in this tier is deterministic and sūtra-citable. Nothing here is a
statistical guess.

| capability | mechanism |
|---|---|
| **Verb-object case government** | A genitive standing as a transitive verb's only argument (भक्तानाम् रक्षति → भक्तान्). Restricted to genitive on principle — see §4.3. कर्मणि द्वितीया (२.३.२) |
| **Upapada case government** | Any wrong case on the word an upapada governs — नमः takes चतुर्थी (२.३.२८), सह takes तृतीया (२.३.१९). This is where instrumental and dative checking works, because the governed word is adjacent and no competing kāraka slot exists |
| **Subject–verb agreement** | पुरुष and वचन, both sides read from real grammatical categories and the correction *derived* via `Vyakarana` on the verb's own dhātu, in the author's own लकार. Covers रामः पठसि, बालकाः पठति |
| **Gender agreement in apposition** | विशेषण–विशेष्य liṅga clash, gated on shared vacana, no clause boundary crossed, neither word an अव्यय |
| **पुरुष consistency** | A first/second-person reading of a word that is also an ordinary nominal is ruled out when no अस्मद्/युष्मद् is present — अस्मद्युत्तमः (१.४.१०७), युष्मद्युपपदे…मध्यमः (१.४.१०५) |
| **Spelling, evidence-gated** | A single lexicon-verified one-edit correction, asserted only when the word's absence from the lexicon is *informative* — i.e. it is not a productively-formed sandhi fusion. Catches संस्क्रुतम्, सन्स्कृतम्, विधालयः, आशिर्वादः, रामेन |
| **Sandhi-fusion recognition** | तथापि, यश्च, चेन्न, विशेषस्तस्य recognised as fused pada pairs and left alone rather than "corrected" |
| **Padānta normalization** | जश्त्व (उपरिष्टाद् = उपरिष्टात्, ८.२.३९), यण् (इत्य् = इति, भवत्य् = भवति, एतास्व् = एतासु, ६.१.७७), visarga, anusvāra |
| **Orthographic variants left alone** | अनुस्वार / homorganic nasal alternation is house style, not error (८.४.५८), with the ययि condition enforced so सन्स्कृतम् is still caught |

**Deliberately at ⚪ review tier, never asserted:** unapplied external sandhi
(padapāṭha style is a legitimate editorial convention), unrecognized words with
no verified fix, and agreement findings resting on an ambiguous morphological
analysis.

---

## 3. Governing principle, stated once

**Never assert an error from absence of evidence.** "I do not recognise this
word" plus "one edit reaches a word I do know" is not grounds for a confident
correction. It becomes grounds only when the word's absence is itself
informative — a simple word missing from a 1.5M-form lexicon is surprising; a
compound or sandhi fusion missing from it is expected, because both are
open-ended and no finite dictionary lists them.

**Five** attempts to patch symptoms downstream of this principle have now been
made, and **all five were reverted after measurement**: edit-distance-2
expansion, a 4+character consonant-deletion guard, the lakāra extension, an
edit-class priority gate and a two-substitution corrector. Each is recorded
with its measured cost in §5. That track record is the reason every
change in this phase was measured against both sets before being kept.

---


## 4. The gap catalogue — everything Vidyut alone cannot close

Each entry states **what triggers it**, **why Vidyut cannot close it**, and
**what would be needed**. The last field is the handover: it says whether the
answer is a different tool, a future phase, an upstream dependency, or a
boundary that no grammar-validation tool can cross.

Every gap here was reached by measurement, not by inspection. Where a fix was
attempted and reverted, the measured cost is in §6.

### 4.1 Compound segmentation ceiling — Chedaka returns nothing

**Triggers.** A long compound the segmenter cannot analyse at all:
दुर्बोधत्वाद्गुरुपादं, परिणामलक्षणा, तदञ्जनत्वाच्छ्रवणो, अष्टापदाकारां,
विध्याचरणं. Chedaka returns either an empty analysis or the token unchanged
with no internal structure.

**Size.** 240 of 491 unrecognized tokens — **48.9% of all unrecognized
material, 14.8% of every token in the corpus.** This is the single largest
contributor to the 30.4% unrecognized rate, and therefore the largest
contributor to the 81.9% review-tier rate.

**Why Vidyut cannot close it.** `vidyut-prakriya` 0.4.0 has **no समास support
whatsoever** — `Samasa` does not exist in the module, verified directly. There
is no derivation path to generate compound forms, and no finite lexicon can
list them, because compounding is productive: the set of well-formed Sanskrit
compounds is unbounded. The Kosha holds 1.5M inflected forms and that is the
wrong shape of resource for an open class. Chedaka is the only segmenter
available, and where it declines there is no second opinion to consult.

**What would be needed.** A dedicated neural compound segmenter — SanskritShala
or DepNeCTI are the named candidates — run as a second engine behind the
existing `GrammarEngine` adapter boundary. **A future phase, not further Vidyut
engineering.** Note the licensing and packaging caveats already recorded
against SanskritShala (no pip package, manual model downloads); that
evaluation has to be redone before adopting it.

### 4.2 Junk-split ambiguity — Chedaka splits, but implausibly

**Triggers.** Chedaka produces a segmentation whose pieces are individually
real words but collectively nonsense: चेन्न → `['ca','it','na']`, अहेतुमन् →
`['aha','it','um','an']`, आर्शीवादः → `['a','ar','Si','iva','Adas']`.

**Size.** 240 of 491 unrecognized tokens (**48.9%**) fall into the A4-veto
bucket, where Chedaka split into 2+ pieces it all claims to know.

**Why Vidyut cannot close it.** Chedaka exposes exactly one method, `run`, and
returns tokens carrying only `text`, `lemma` and `data`. **There is no score,
probability or confidence on a split** — verified directly against the Python
bindings. So the engine cannot distinguish a good split from a junk one, and
the A4 veto therefore refuses to trust *any* of them for the purpose of
asserting an error. That is the correct trade — it is what stops शनैर् being
"corrected" to शणैर् — but it means these tokens stay permanently unrecognized
and permanently at review tier.

**What would be needed.** Split-plausibility scoring: either a segmenter that
returns calibrated confidence, or a language model over segment sequences.
**A future phase.** Concretely *not* worth attempting: hand-written
plausibility heuristics over split shapes, which is the same unmeasurable
guesswork that produced three separate reverts in this project.

### 4.3 Kāraka scope boundary — case roles beyond genitive and narrow upapada

**Triggers.** Wrong case on a verb's argument where the case is not genitive:
रामः गुरुः नमति (→ गुरुम्), गुरुः शिष्यं ज्ञानं ददाति (→ शिष्याय),
बालकः कक्षां पठति (→ कक्षायां). Gold cases 2-22, 2-23, 2-30, 2-32.

**Why Vidyut cannot close it.** This was attempted and produced a real false
positive, which is what defines the boundary rather than merely suggesting it.
Generalising the verb-governed check to all cases immediately flagged
**बालकः कक्षायां पठति** — "the boy reads *in the classroom*", entirely correct
— because कक्षायाम् was the sole non-nominative nominal and पठ् governs
द्वितीया. The reason is structural: तृतीया can be करण, सप्तमी अधिकरण, पञ्चमी
अपादान. Those are independent kāraka roles that legitimately **coexist** with
the कर्म. Deciding whether a given oblique fills the object slot or an adjunct
slot is exactly the binding information morphology does not carry.

षष्ठी is the principled exception and is why the genitive check ships:
शेषे षष्ठी (२.३.५०) *defines* it as the non-kāraka remainder, so a genitive in
an argument slot cannot be an adjunct and is confirmable. Upapada government
(नमः → चतुर्थी, २.३.२८; सह → तृतीया, २.३.१९) ships for the same reason — an
upapada fixes the case of the word beside it outright, leaving no competing
slot.

**What would be needed.** A dependency parser, to say which nominal binds to
which predicate. **That re-measurement has now been done, and the answer is
no — see §4.11.** This entry stays open, but a parser is no longer the
candidate answer to it.

### 4.4 Gender-agreement and participle edge cases

**Triggers.** Two distinct shapes, both currently silent:

1. **Bare nominal apposition with an action verb absent from the pair's
   clause** — सुन्दरी बालकः, एषः नदी (gold 5-48, 5-51).
2. **Participle–subject gender via a copula** — बालिका पठन् अस्ति.

**Why Vidyut cannot close it — two independent causes, both measured.**

- The masculine शतृ nominative singular ends in **-न्** (पठन्, गच्छन्).
  `_prathama_lingas` only accepts tokens ending in `H / m / M / A / I`, a guard
  that exists so a bare unsandhied compound stem is not read as a standalone
  nominative. पठन् therefore returns *no liṅga at all* and the pair is never
  tested. The information is present in the Kosha; the guard is what blocks it.
- Where a participle *is* reachable, it is frequently genuinely ambiguous:
  पठन्ती is Stri/प्रथमा/एक **and** Napumsaka/प्रथमा/द्वि at top rank, so the
  existing ambiguity gate correctly declines to assert.

**What would be needed.** The first cause is **category 1 and Vidyut-reachable**
— it widens an ending guard. It was deliberately *not* attempted in the closing
round because that guard's entire purpose is false-positive suppression, and
widening it needs its own measure-and-revert cycle rather than being appended
to a closing pass. The second cause is real morphological syncretism and is not
fixable by widening anything. **Deferred, with a named starting point.**

### 4.5 `eka` is not सर्वादि — an upstream library defect

**Triggers.** एकस्मिन्, एकस्मै, एकस्मात्, and feminine एकस्यै / एकस्याः /
एकस्याम्. Gold 15-155/156/157.

**Why Vidyut cannot close it.** एक is a member of the सर्वादि gaṇa
(सर्वादीनि सर्वनामानि, १.१.२७) and should take सर्वनाम endings. vidyut declines
it as a plain a-stem in **both** `prakriya` and `kosha` — एकाय / एकात् / एके.
All 25 सर्वादि stems were audited: sarva, viśva, anya, itara, pūrva and 17
others are correct; **only `eka` is affected**, which is what makes it look
like a missing gaṇapāṭha entry rather than a rule bug.

**Status.** These forms are now correctly **never mis-corrected** — the
word-initial deletion guard stops एकस्मिन् being "fixed" to कस्मिन् — but they
remain unrecognized and sit at review tier.

**What would be needed.** An upstream fix. Complete reproduction, full
masculine and feminine paradigm tables, the 25-stem audit and a suggested patch
are in [`vidyut-issue-eka-sarvadi.md`](vidyut-issue-eka-sarvadi.md).
**Outside this project's control — track, do not patch locally**, since a local
override would diverge from the library and mask the upstream fix when it
lands. Filing was blocked in this environment (no `gh`, no credentials, and the
API route refused); the user holds the filing action. *(Issue link to be
recorded here once filed.)*

### 4.6 Apposition / possession ambiguity — a boundary, not a gap

**Triggers.** रामः पिता आगच्छति ("Rama, the father, comes" — apposition,
समानाधिकरण, २.३.४६) versus रामस्य पिता आगच्छति ("Rama's father comes" —
genitive). Gold 2-26.

**Why no tool can close it.** Both readings are fully grammatical and mean
different things. Nothing in the text distinguishes them; only the author knows
which was meant. Flagging the first would be asserting an error against correct
Sanskrit on the strength of a guess about intent.

**What would be needed.** Nothing — this is **permanently out of scope for any
grammar-validation tool, by definition.** In the closing round gold case 2-26
was retagged from `verdict=error` to `verdict=correct` to stop the suite
scoring a correct sentence as a missed detection.

### 4.7 Real words that are also typos — unreachable by any spelling mechanism

**Triggers.** राम गच्छति (intended रामः), बालक गच्छति (बालकः), गुरुः शिष्य
शिक्षयति (शिष्यं), प्रथना (प्रार्थना), परिक्षा (परीक्षा). Gold 1-01, 1-02,
1-03, 1-08, 1-20, 13-137.

**Why Vidyut cannot close it — and this one is easy to misdiagnose.** These
look like missing-character typos, and the closing round was scoped to build
insertion repair for exactly them. Measurement showed the premise is wrong:
**राम, बालक, शिष्य, प्रथना and परिक्षा are all real, recognized words in the
Kosha.** राम and बालक are प्रातिपदिकs and vocatives; प्रथना is a real word with
lemma प्रथन; परिक्षा is listed outright. The spelling corrector only ever runs
on tokens the lexicon does *not* recognise, so it never sees them — and it must
not, because asserting a spelling error against a word that is in a 1.5M-form
lexicon is precisely the over-flagging this project exists to avoid.

Catching राम गच्छति would require a syntactic rule — "a finite verb with no
overt nominative" — which **directly conflicts with a shipped guarantee**: gold
15-151/152/153 (ग्रामे गच्छति, वने वसति, गृहे तिष्ठति) are correct sentences
with elided subjects that must not be flagged. And राम गच्छति is itself
readable as a vocative: "O Rama, he goes."

**What would be needed.** Author intent. **Permanently out of scope**, same
category as §4.6.

### 4.8 Ambiguous spelling candidates with no disambiguator

**Triggers.** Genuinely unrecognized misspellings where several lexicon-valid
corrections exist: प्रर्थना → {प्रार्थना, प्रथना, पर्थना}; अध्यनम् →
{अध्ययनम्, अध्यनमम्, अधनम्, अयनम्, धयनम्}. Gold 1-18, 13-138.

**Why Vidyut cannot close it.** The correct candidate **is** generated and
**is** recognized — the single-candidate gate rejects the set because more than
one member validates. Choosing between them needs a frequency prior, and
**vidyut exposes no frequency or probability data anywhere**: `Chedaka` has only
`run`; `Token` carries only `text`/`lemma`/`data`; `PadaEntry` has no frequency
field; the cheda model ships as an opaque msgpack with no query API. The only
offline corpus available is the evaluation corpus itself, and deriving counts
from it would contaminate every measurement this project relies on.

Two substitutes were built and measured in the closing round, and both failed —
see §5.2 and §5.3.

**What would be needed.** A frequency table from a corpus that is **not** the
evaluation set, or a language model that can score a candidate in context.
**A future phase** — and note that this gap is worth far less than §4.1/§4.2:
it accounts for roughly 10 tokens in 1617.

### 4.9 Unapplied vowel sandhi is not flagged — newly surfaced

**Triggers.** विद्या आलयः, महा उत्सवः, देव इन्द्रः, नर इन्द्रः, सुर ईशः,
गण ईशः (gold 7-69 … 7-74). All are correct as padapāṭha but represent an
unapplied sandhi opportunity that the tool is expected to *offer* at review
tier.

**How it surfaced.** The Part B harness audit added a strict sub-count to
`evaluate_gold.py`: of the 39 passing `expected=review` cases, only **19 raise
an actual advisory — 20 are silent.** The metric had always been defined as
"must not be asserted as a hard error", which silence satisfies, so this never
showed. Of the 20, most are legitimately silent (compounds and place names that
genuinely *are* valid words: राजपुरुषः, नीलकमलम्, वाराणसी). But six are a real
coverage gap: **the sandhi checker covers visarga junctions and not vowel
junctions** — रामः गच्छति and रामः अस्ति are correctly offered, विद्या आलयः is
not.

**Why it was not fixed here.** It is plausibly Vidyut-reachable — a `sandhi`
data directory ships with the library. It was **not** attempted because the
closing round's Part A scope was explicit, because a new advisory class adds
review-tier volume to an already-81.9% review rate, and because it warrants its
own measure-and-revert cycle. **This is the highest-value remaining
Vidyut-reachable item and should be the first candidate in any follow-up
Vidyut work.**

### 4.11 The parser was re-measured against improved tags, and closed (2026-09-11)

§4.3 asked for the dependency-parser decline to be re-measured "with the verb
layer as it stands now", on the reasoning recorded in the dependency-parsing
phase doc that the blocker was **verb invisibility upstream, not the parser**.
That was done. **The reasoning was wrong, and the decline stands for a
different reason.**

**What was changed first.** Four tagging defects in the CoNLL-U bridge, each
measured before and after: कृदन्त participles tagged NOUN, indeclinables tagged
NOUN, oblique pronouns tagged NOUN (all three were the same bug — real
information available and discarded by branch ordering), plus लङ् added to
`VerbGrammar`. Bridge UPOS agreement went **34.3% → 47.2%**, coarse
**48.9% → 64.1%**, the verb gap **233 → 156**, and Case/Gender/Number
precision **69.4/59.0/80.9% → 84.1/79.6/87.9%**.

**What that bought the parser.** Measured by 10-fold CV over the same 225
sentences / 1445 tokens, with the tag columns as the only variable:

| metric | before | after | gold tags (ceiling) |
|---|---|---|---|
| UAS | 48.72% | **51.76%** | 60.48% |
| LAS | 32.11% | **34.53%** | 48.65% |
| nsubj recall | 37.3% | **40.5%** | 56.9% |
| post-verbal subject, right verb | 4.2% | **12.5%** | 18.8% |
| **subject precision** | **25.1%** | **25.3%** | **33.7%** |

The tagging work is real — UAS +3.0, and post-verbal head attachment tripled.
It closes about a quarter of the gap to perfect tags.

**Why it is still closed.** Subject precision did not move: 25.1% → 25.3%.
And with **gold** tags it is only **33.7%** — a ceiling no tagging work can
reach past. `job_metrics.py` states the bar itself: "a check gated on a
spurious subject is a new false positive." At 25% precision three of four
proposed subjects are wrong, so a 🔴 check gated on it is a false-positive
generator, which is what §5's five reverts exist to prevent.

**The durable correction.** The dependency-parsing doc's conclusion that verb
coverage is "a prerequisite, not a follow-on" is **not supported**: verb
coverage improved substantially and the binding constraint did not move.
The constraint is the parser's own precision on 230 sentences of training data.

**Also settled in the same pass, so it is not re-proposed:**

- **Kosha-missing कृदन्त forms (a "Tier 2" `KrdantaGrammar`)**: built as a
  prototype and measured — **13.6 s of cold start to fix 0 of 109 tokens.**
  The remaining VERB→X bucket is not participles; it is ~57% sandhi-fused
  multi-word tokens (`ko'pyupAyo'nuzWIyatAm`), 38% prefixed verbs, and other
  lakāras. Do not build this.
- **Full lakāra coverage**: the whole 11 × 2 space costs 14.3 s of cold start
  and is worth 39 tokens. Measured per combination: लङ् 11 tokens/0.53 s,
  लोट् 6/0.59, लट्-कर्मणि 5/0.33, लोट्-कर्मणि 5/0.35, लृट् 5/0.49,
  लिट् 5/1.16. **लङ् only was kept.** The other four were added, measured,
  and reverted: they cost 2.6 s of cold start and left the product's
  unrecognised-token rate at **515/1617 (31.8%), unchanged to the token**,
  because the Kosha already carries those forms.
- **उपसर्ग/prefix support**: `Dhatu.with_prefixes()` works correctly
  (अनु + स्था → अनुष्ठीयते, retroflexion and all), but a prefixed index costs
  ~11.7 s per lakāra and is worth 8 tokens. Prefix-stripping against the
  existing index is nearly free but worth only 2.

**What this leaves.** Every road in this pass ended at the same place: roughly
two-thirds of the remaining tag gap is sandhi-fused compound tokens, which is
§4.1/§4.2. **Compound segmentation is the next real lever, and nothing else
comes close.**

### 4.10 No proper-noun tag in the library

**Triggers.** A proper noun that collides with a verb paradigm cell — भरतः is
a name *and* a well-formed प्रथम-द्विवचन of भृ.

**Why Vidyut cannot close it.** `PratipadikaEntry` has exactly two variants,
`Basic` and `Krdanta`. There is **no नामविशेष / संज्ञा field anywhere** on
`PadaEntry` or `PratipadikaEntry`, verified directly.

**Status: worked around, not open.** The engine gets the right answer by a
different route — a genuine तिङन्त's only nominal homographs are कृदन्त forms
of its own root, so a candidate with an independent `Basic` प्रथमा reading
yields to one without. Recorded here because the obvious fix ("rank proper
nouns higher") is not implementable and should not be re-proposed.

---
## 5. Attempted and reverted, with measured cost

Five expansions of the checker have now been built, measured and reverted.
They are recorded in full because the pattern is the most reusable finding in
this project: **every attempt to widen recall on unrecognized words has cost
more in false positives than it gained in detections, on real prose, every
time.** The unrecognized-token population in running Sanskrit is dominated by
words that are correct but unlisted, so anything that turns "unrecognized"
into "corrected" is operating on a base that is mostly right already.

| # | attempt | gain | cost | verdict |
|---|---|---|---|---|
| 1 | Edit-distance-2, general operations | — | reached coincidental real words (सोऽपि → ओपि, असामान्यशब्दः losing its नञ्) | reverted |
| 2 | 4+ character consonant-deletion guard | — | rejected on principle, then found still live in the code and removed in Phase B | reverted |
| 3 | Lakāra extension (all 10 lakāras × kartari/karmani) | 0 recall | gold 43/43 → 42/43, DCS FP 8.5% → 11.9% | reverted |
| 4 | **Edit-class priority gate** (closing round) | +1 gold | **DCS FP 6.5% → 8.5%**, plus a review→error regression | reverted |
| 5 | **Two composed phonetic substitutions** (closing round) | +1 gold | **DCS FP 6.5% → 8.1%** | reverted |

### 5.1 Why the closing-round attempts were made at all

Both were specified as narrower redesigns of attempt 1, on the reasoning that
its failure came from *general* edit operations. That reasoning was correct as
far as it went — attempt 5 does fix the three named failure modes of attempt 1
(सोऽपि, असामान्यशब्दः and पुस्तकनाम all correctly decline under it). The
failure is elsewhere, and neither narrower design escapes it.

### 5.2 Attempt 4 — edit-class priority

**What was tried.** Replace "exactly one lexicon-valid candidate overall" with
"exactly one within the highest-priority edit class that matches anything",
ordering classes vowel-length → visarga/anusvāra → haplography → consonant →
transposition → deletion, on the theory that a vowel-length slip is a likelier
typo than a deletion.

**Measured cost.** Gold in-scope 139/155 → 140/155 (13-138 प्रर्थना caught).
DCS false positives **17/260 (6.5%) → 22/260 (8.5%)**. Gold known-gap 6-56
(`रामः अगच्छति।`) regressed from review to **error** — a false 🔴.

The false corrections it produced on correct prose include
**शनैर् → शणैर्** (the exact case the A4 veto was written to prevent),
अर्थत → अर्थतः, चान्यद् → चान्याद्, चोक्तं → चोकं (which is च + उक्तं),
चत्वार → चत्वर, सूर्प → शूर्प, उवर्णः → ऊवर्णः, तस्या → तास्या.

### 5.3 Attempt 5 — two composed phonetic substitutions

**What was tried.** Exactly two substitutions drawn from the phonetic
confusion classes — no transpositions, no insert/delete paths — tried only as
a fallback when the single-edit path found no unique candidate, still gated on
exactly one valid result. The word-initial guard was kept.

**The second safeguard could not be built.** Frequency-based disambiguation
("prefer a candidate only when its corpus frequency is substantially higher
than the original's") has no data source — see §4.8. The attempt therefore ran
with one safeguard instead of two, which is stated rather than hidden.

**Measured cost.** Gold in-scope 139/155 → 140/155, no gold regression. DCS
false positives **17/260 (6.5%) → 21/260 (8.1%)**. It still produced
शनैर् → शणैर्, वर्षेन → वर्शेन, तस्या → तास्य, अपराह्णिकं → आपराह्णिकं,
मन्यन्ते → मन्यते and भजन्ते → भजते — the last two rewriting perfectly good
plural verbs into singulars.

It also exposed a subtler defect: for प्रर्थना it suggested **प्रार्थन**, the
stem, not प्रार्थना. The gold case scored as a pass because the harness checks
which surface was flagged, not what the suggestion said.

### 5.4 What a future attempt would need to do differently

Not a narrower edit model — that has now been tried twice from two directions.
It needs **an independent source of evidence about which candidate is right**:
a frequency prior from a corpus that is not the evaluation set, or a language
model scoring the candidate in its sentence context. Without that, the
single-candidate gate is not a limitation to be engineered around; it is the
only thing standing between the tool and the ~9-to-1 false-correction ratio
measured above.

---

## 6. Harness corrections made in this phase

Three measurement defects were found and fixed. None changed engine behaviour;
all changed what the harnesses could report. They are recorded because two of
them had the power to mislead a future round.

### 6.1 Severity aggregation in the DCS harnesses

`run_exp1.py` computed review-severity syntax findings, used them for
`has_review`, then never serialised them — so the file answered "0" to any
question about review-tier syntax counts. Fixed with a separate
`review_syntax_issues` array plus `syntax_issues_error` /
`syntax_issues_review` summary counts. Kept **separate** from `syntax_issues`
because that field defines `is_false_positive`, and every false-positive rate
on record was computed with it error-only; merging would have silently
redefined the project's headline metric.

`run_exp2.py` had the mirror defect — it serialised every syntax issue but
recorded no severity. Now records `severity`. Its recall figures were always
computed from a correctly filtered set, so no reported number was affected.

Re-derivation across rounds with the corrected aggregation gave review-severity
syntax counts of **8 → 8 → 7** for rounds 2 → 3 → 4. **No past claim changed**:
every figure on record was either error-severity, or measured outside the
harness.

### 6.2 `diagnose_recognition.py` measured a different thing than the product

It called `engine._is_recognized`, which consults the lexicons only, while the
product's recognition path is `check_word` — which additionally accepts a
तिङन्त derived by VerbGrammar from the Dhātupāṭha and an अव्ययीभाव/उपसर्ग
compound recognised from its members. That is the whole of the 30.6% / 30.4%
discrepancy. The diagnostic now calls `check_word` and reports **30.4%**,
matching the pipeline.

**30.4% is authoritative.** No past claim changes: every report already used
the pipeline figure; 30.6% appeared only in raw diagnostic output.

### 6.3 `evaluate_gold.py` scored silence as a passing review

`expected == "review"` passed on `verdict != "error"`, which total silence also
satisfies. That test was written before the engine had a review tier at all and
was never updated when Phase C added one. The headline metric is deliberately
**unchanged** — it stays comparable with every figure on record — but the
report now prints `got=review` rather than `got=correct` when an advisory was
actually raised, and adds a strict sub-count. That sub-count is what surfaced
§4.9: **19 of 39 raise an advisory, 20 are silent.**

---
## 7. The review-tier rate: an understood characteristic, not a defect to chase

**81.9% of DCS sentences carry at least one review-tier advisory.** This was
audited rather than assumed. Composition of all 501 review-tier flags,
re-measured at phase close:

| source | flags | share |
|---|---|---|
| unrecognized words (`invalid`) | 477 | **95%** |
| unapplied external sandhi | 10 | 2% |
| ambiguity-demoted agreement findings (token + syntax) | 14 | 3% |

A hand-classified random sample of 40 of the 483 distinct unrecognized forms:

- **~29 (72%) are compounds** — जनसंद्रावेषु, शरीरपुर्यष्टकादिवद्बोधसंकोचकत्वम्,
  सर्वविकारसंपदव्यक्तता, प्रतोदधूमायनदाहचोषवान् …
- **~7 (18%) are sandhi fusions** — व्यासेनोपदेक्ष्यति, अभ्यागच्छतीति, खल्विदम् …
- **~4 (10%) are lexicon gaps** — mostly `-तस्` adverbs (शनैस्, अर्थतः and
  similar अव्ययs simply absent from the Kosha).

**None were misclassified by overcautious gating.** They are in review because
they are genuinely unrecognized and the engine correctly declines to assert
anything about them. All 14 ambiguity-demoted agreement flags were also
examined individually: every one sits on correct text, and every one would
have been an asserted false positive without the demotion. They account for
roughly one sentence of the 81.9%, so they are immaterial to the headline.

This traces directly to the **30.4% unrecognized-token rate**, which is itself
48.9% unsegmentable compounds and 48.9% Chedaka junk-splits vetoed by A4
(§4.1, §4.2). Reliable compound-member segmentation is not available from
vidyut here: splitting against the Kosha's own 168,878 stems was measured and
is **vacuous** — it "decomposes" गुरुः as guru+H and पठति as paWa+ti, and
produces वानूपजलजा = वा+नू+प+जलजा.

**Documented as a known product characteristic tied to the compound-
segmentation ceiling. No further guard or heuristic should be added to
suppress this volume** — that is precisely the mistake made and reverted five
times (§5). The honest fix is better segmentation or a larger lexicon, not a
filter over the symptom.

A caveat that belongs with the numbers: **the 13% multi-letter-typo recall is
not a quality signal.** The catches propose the *wrong* correction
(गृहीत्क → गृहीत, not गृहीत्वा). It measures how often a two-edit corruption
drifts within one edit of some unrelated real word.

---


## 8. Closing regression record (2026-09-06)

Full suite re-run after every change in this round. **No regression.**

| metric | round-4 close | **phase close** | note |
|---|---|---|---|
| Gold in-scope pass rate | 138/155 | **139/155 (89.7%)** | +1 from the 2-26 retag |
| Gold error recall | 44/61 | **44/60 (73.3%)** | denominator −1: 2-26 is no longer an error case |
| Gold false-positive avoidance | 55/55 | **56/56 (100%)** | +1: 2-26 moved here |
| Gold review not mis-asserted | 39/39 | **39/39 (100%)** | unchanged |
| Gold known-gap | 15/16 | **15/16** | unchanged |
| DCS false-positive rate | 6.5% | **6.5% (17/260)** | unchanged |
| DCS syntax findings, error / review | 3 / 7 | **3 / 7** | unchanged |
| DCS review-only | 81.9% | **81.9%** | unchanged |
| DCS fully clean | 11.5% | **11.5%** | unchanged |
| Unrecognized-token rate | 30.4% | **30.4%** | unchanged; diagnostic now agrees |
| Exp-2 overall recall | 15/206 | **15/206 (7.3%)** | unchanged |
| Frontend build | ✓ | **✓ 288 ms** | unchanged |

**Per-test comparison:** the pass/fail outcome of all 171 gold cases was
diffed against the pre-round baseline after every individual change. The only
per-test movement in the whole round is `2-26 FAIL → PASS`, which is the
intended effect of the retag. Both reverted experiments were confirmed to
restore an outcome-for-outcome identical suite before proceeding.

**Regression-guard sections, all passing:**

| section | | section | |
|---|---|---|---|
| 7. Sandhi | 13/13 | 12. Unicode / Devanagari | 10/10 |
| 8. Sandhi splitting | 10/10 | 15. Locative adjuncts & सर्वादि obliques | 7/7 |
| 9. Compound / समास | 4/4 | 16. Coordinated subjects | 5/5 |
| 11. Correct Sanskrit — MUST NOT FLAG | 18/18 | 17. Verb/noun homograph & unrecognized subject | 5/5 |
| 3. Number / वचन | 8/8 | 18. अस्-stem vs अ-stem -आः vacana | 4/4 |

---

## 9. Handover — what the next phase actually needs to solve

Ordered by measured value, not by how interesting the problem is.

1. **Compound segmentation (§4.1) and split plausibility (§4.2).** Together
   these are **97.8% of all unrecognized material** and the direct cause of the
   81.9% review-tier rate. Nothing else comes close. A compound segmenter that
   returns calibrated confidence would address both at once. This is the single
   highest-value item in the entire backlog.
   **Planned 2026-09-17 as stages C0–C8 and closed the same day: C4 and C5a shipped at ⚪, the rest measured and not built — see §10.11. The segmentation need itself is unchanged.**
2. ~~**Dependency parsing (§4.3).**~~ **CLOSED 2026-09-11 — see §4.11.**
   Re-measured with a substantially improved verb/tag layer (bridge UPOS
   34.3% → 47.2%). Subject precision did not move (25.1% → 25.3%) and its
   ceiling with *gold* tags is 33.7%, far below what a 🔴 gate can rest on.
   The "verb invisibility is the prerequisite" reasoning was tested and
   disproved. Do not re-open without a fundamentally larger treebank.
3. ~~**Vowel sandhi advisories (§4.9).**~~ **DONE 2026-09-10.** Implemented in
   `check_junction`, routing गुण (६.१.८७) / वृद्धि (६.१.८८) / यण् (६.१.७७) /
   सवर्ण-दीर्घ (६.१.१०१) per the rule that actually fired. **All 6 of the
   §4.9 cases now raise an advisory**; gold advisory sub-count 19 → 27 of 39,
   with gold pass rate, every gold category and the DCS false-positive rate
   unchanged throughout.

   The last 3 (नर इन्द्रः, सुर ईशः, गण ईशः) needed a second fix, completed
   2026-09-15: `check_text`'s bare-stem promotion was rewriting an a-final
   word to its -अस् form *before* the junction was judged, and विसर्ग before
   a vowel other than short अ leaves no visible trace, so the promoted form
   produced no advisory while blocking the गुण reading that does. The
   promotion is now skipped before a non-अ vowel — नर + इन्द्रः → नरेन्द्रः
   (आद्गुणः ६.१.८७), सुरेशः, गणेशः. Short अ deliberately keeps the promotion,
   because there the विसर्ग reading is the correct one: राम + अपि is रामोऽपि
   (६.१.११३), not the सवर्ण-दीर्घ रामापि a bare stem would propose.
4. **Participle liṅga agreement (§4.4).** Category 1 and Vidyut-reachable for
   half its cause; touches an existing false-positive suppression guard, so it
   needs a dedicated cycle.
5. **Spelling disambiguation (§4.8).** Worth roughly 10 tokens in 1617. Do not
   attempt without an independent frequency or language-model prior — see §5.4.
6. **Track `eka` upstream (§4.5).** No local work; watch for the fix.

**Permanently out of scope, and not to be revisited as gaps:** apposition
versus possession (§4.6) and real-words-that-are-also-typos (§4.7). Both need
author intent, which no grammar-validation tool can supply.

**The discipline that produced these numbers should carry into the next
phase**: every change measured against both sets before being kept, reverted
on any false-positive increase, and no heuristic shipped that has not been
measured against real prose. Five reverts (§5) are the evidence that this is
not ceremony.

## 10. Samāsa phase plan (2026-09-17)

Supersedes the "a segmenter with calibrated confidence" framing of §9 item 1
as the *route*; the goal is unchanged.

### 10.1 Findings this plan rests on

- **`all_known` carries no information.** Over the 477 unrecognised DCS tokens,
  the 234 that Chedaka splits into 2+ pieces and the 234 whose pieces are all
  "known" are the *same* tokens: Chedaka only returns splits it recognises.
  The Kosha also returns entries for junk pieces (`Fm`: 6 entries), so lexicon
  presence cannot reject a split either.
- **A shape test does discriminate.** "Does this piece's surface equal its own
  prātipadika?" separates `rAja` (stem, 1 reading) from `rAjYas` (inflected,
  0) and rejects the junk piece `Fm` (0). This is सुपो धातुप्रातिपदिकयोः
  (२.४.७१) read positively — non-final members are bare stems. It is a filter
  on whole splits, not a per-piece oracle: `aka` passes as a stem, and
  `अकर्मनिमित्ते → aka+Fm+animitte` dies only because its other pieces fail.
- **SanskritShala's compound module (SaCTI) cannot detect errors.** Its input is
  a compound *already split* into members; its output is one of 4 coarse / 15
  fine types; it has no "invalid" output. Apache-2.0.
- **SanskritShala's segmenter (TransLIST) cannot run in-process.** F1 98.9%
  (SIGHUM) / 97.6% (Hackathon), but it needs Python 3.7, a conda env, and
  installs by copying patched files into `fastNLP`'s site-packages. Viable
  only as a one-off offline harvester; parked.
- **Current behaviour on real samāsa errors.** `राज्ञःपुरुषः`, `रामलक्ष्मणः`,
  `पुरुषराजः` → ⚪ review, indistinguishable from their correct counterparts
  and from junk (`गजपुस्तकनदी`). `पीताम्बरः बाला`, `उपकृष्णः` → silent.
  `KNOWN_SAMASAS` (6 hardcoded entries) only populates a display list and
  never raises a finding.

### 10.2 What is reachable, by compound type

An error is decidable from form only when the written form is wrong under
**every** type the compound could be. The same string is often several types
(`पीताम्बरः`: कर्मधारय "yellow cloth" / बहुव्रीहि "he whose cloth is yellow").

| Type | Reachable from form | Tier ceiling |
|---|---|---|
| अव्ययीभाव | mostly — indeclinable first member is a visible marker; -म् ending, vowel shortening, indeclinability | ⚪, some 🔴 |
| तत्पुरुष (incl. कर्मधारय, द्विगु) | partly — महा, samāsānta, last-member gender, द्विगु number | mostly ⚪ |
| द्वन्द्व | partly — number and gender; a तत्पुरुष reading can never be excluded | ⚪ only |
| केवल | only the rule shared by all types (२.४.७१) | 🔴 where no exception |
| बहुव्रीहि | not reachable — agreement follows an external referent | — |

Type *labelling* from form works only for अव्ययीभाव and द्विगु.

### 10.3 Rules for every stage

- One stage at a time, with approval before the next.
- Gold and DCS run before and after, compared per test. Any regression is
  reported, not explained away.
- **🔴 only if** the finding fires on none of the 260 DCS sentences and is
  silent on every correct sentence in the samāsa test set. Otherwise ⚪, or
  not shipped.
- Cold start checked every stage.
- Each finding gets its own margin message (extend `reviewReason` in the
  frontend), never the generic lexicon line.

### 10.4 Stages

| Stage | What | Kind | Tier |
|---|---|---|---|
| C0 | Samāsa test set + baseline | setup | — |
| C1 | Test the shape check (measurement only) | **go/no-go** | — |
| C2 | Recognise well-formed compounds | cuts noise | — |
| C3 | Case ending kept inside a compound (२.४.७१) | error | 🔴 if clean |
| C4 | अव्ययीभाव ending rules | error | ⚪, maybe 🔴 |
| C5 | तत्पुरुष form rules (महा, samāsānta) | error | 🔴 if clean |
| C6 | Compound takes gender of last member | error | ⚪ |
| C7 | Collective द्विगु must be singular | error | ⚪ |
| C8 | द्वन्द्व number | error | ⚪ |

**C0 — Samāsa test set and baseline.** Gold has almost no samāsa cases, so
precision for C3–C8 cannot be measured without new ones. A self-written set
with a wrong form and its correct counterpart for every rule, plus the correct
forms each rule could wrongly flag: अलुक् compounds (`सरसिजम्`, `युधिष्ठिरः`,
`वनेचरः`, `परस्मैपदम्`), `उपाध्यायः` (उप-initial, not अव्ययीभाव), `पाणिपादम्`
(correct neuter-singular द्वन्द्व), बहुव्रीहि with unusual gender. Baseline
already measured: gold 139/155, DCS FP 17/260 (6.5%), review-only 83.1%,
unrecognised 477/1617, 234 split.

**C1 — Shape check, measurement only.** Non-final members bare stems, final
member inflected. Run over the 477 unrecognised DCS tokens and hand-check a
sample. Report correct compounds accepted, junk splits rejected
(`अकर्मनिमित्ते`), and meaningless compounds accepted (`गजपुस्तकनदी`).
**If it cannot separate correct compounds from junk reliably, stop** — every
later stage depends on it.

**C2 — Recognition.** A shape-valid token leaves the review list, or at
minimum gets "Likely a compound" (chosen from the C1 numbers). Review rate
should fall; DCS FP must not rise; gold unchanged. Known cost: meaningless
compounds also go quiet.

**C3 — Case ending retained (सुपो धातुप्रातिपदिकयोः २.४.७१).**
`राज्ञःपुरुषः` → `राजपुरुषः`. Exempt अलुक् compounds (६.३.१ ff.).

**C4 — अव्ययीभाव.** Detected by an indeclinable first member (उप, अनु, प्रति,
यथा, सह…). 4a: ends in -म् (नाव्ययीभावादतोऽम्त्वपञ्चम्याः २.४.८३), allowing
optional -ात्. 4b: final long vowel shortened, `उपगङ्गम्` (ह्रस्वो नपुंसके
प्रातिपदिकस्य १.२.४७) — best 🔴 candidate. 4c: no declined ending (अव्ययीभावश्च
१.१.४१). Default ⚪ because of `उपाध्यायः`-type forms; sub-rules measured
separately.

**C5 — तत्पुरुष form rules, each measured separately.** 5a: `महत्पुरुषः` →
`महापुरुषः` (आन्महतः समानाधिकरणजातीययोः ६.३.४६). 5b: `महाराजा` → `महाराजः`
(राजाहस्सखिभ्यष्टच् ५.४.९१).

**C6 — Last-member gender (परवल्लिङ्गं द्वन्द्वतत्पुरुषयोः २.४.२६).**
`राजकन्यः` → `राजकन्या`. ⚪ only — a बहुव्रीहि may take another gender.

**C7 — Collective द्विगु singular (द्विगुरेकवचनम् २.४.१).** Numeral first
member. ⚪ only — बहुव्रीहि such as `पञ्चाननः` look identical.

**C8 — द्वन्द्व number.** Separate-item द्वन्द्व is dual for two members,
plural for three+; collective is neuter singular. `रामलक्ष्मणः` fits none. ⚪
only — a तत्पुरुष reading cannot be excluded; member count depends on C1.

### 10.5 Not in this plan

- बहुव्रीहि agreement, member order, meaningless compounds — need meaning.
- Compound type labels (SaCTI) — a label changes no finding.
- TransLIST in-process — Python 3.7 + patched `fastNLP`; offline harvest parked.
- Any DCS-derived data — DCS has no licence.

### 10.6 C0 results (2026-09-17)

**Built.**
- `scripts/build_samasa_dataset.py` → `tests/gold/samasa.json`: 49 self-written
  cases, same schema as the main gold set. 33 correct sentences (in scope from
  day one, guarding the 🔴 gate) and 16 wrong forms (known gaps until their
  stage ships). Section numbers 101–108, so they can never collide with gold.
- `scripts/evaluate_gold.py --dataset <file>`: optional flag, default
  unchanged. Main gold re-run afterwards is **byte-identical** to the previous
  run (139/155).

**Baseline — correct sentences (33).**

| Outcome | Count |
|---|---|
| clean | 13 |
| ⚪ review noise | 19 |
| 🔴 false positive | **1** |

⚪ noise by section: correct compounds 6/8, C3 negatives 5/8, C4 2/5,
C5 0/3, C6 2/2, C7 2/3, C8 2/4.

**The one 🔴 is pre-existing and not samāsa-related.** `मातापितरौ नमामि।` —
and equally `पितरौ नमामि।` — is flagged as a subject-verb agreement error.
`नमामि` is उत्तम पुरुष, so its कर्ता is an unstated अहम् (अस्मद्युत्तमः
१.४.१०७); `पितरौ` is the object, whose dual accusative is spelled like the dual
nominative. The agreement check takes it as the subject. `अहं मातापितरौ
नमामि।` is clean. Logged, not fixed in C0; it needs its own cycle in
`karaka_syntax.py`, with gold and DCS measured.

**Fixed 2026-09-17, as its own step before C1.** When every reading of the
verb is उत्तम or मध्यम पुरुष, its कर्ता is an unstated अहम्/त्वम्, so a nominal
whose Prathamā is spelled like its own Dvitīyā — same prātipadika, liṅga and
vacana (every dual in -औ, every neuter in -म्) — can be the verb's object, and
no agreement error is asserted. New helper
`KarakaSyntaxEngine._prathama_is_also_dvitiya`. `रामः पठसि।` (gold 6-53) keeps
its 🔴: रामः has no Dvitīyā reading. The change can only remove findings.

| | Before | After |
|---|---|---|
| Gold | 139/155 | **byte-identical per test** |
| Samāsa set, correct sentences | 32/33 | **33/33** |
| DCS false positives | 17/260 (6.5%) | 17/260 (6.5%) |
| DCS syntax findings | 3 🔴, 5 ⚪ | 3 🔴, 5 ⚪ — none removed |

Probe: `पितरौ नमामि।`, `वनं पश्यामि।`, `फलानि खादसि।`, `बालकौ पठामि।` now clean;
`रामः पठसि।`, `रामः पठामि।`, `बालकः पठामि।` still 🔴.

**Baseline — wrong forms (16).** No wrong form gets a finding specific to its
rule. 14 get a generic ⚪ (lexicon or sandhi note) that looks the same as the
noise on their correct counterparts, and 2 are completely silent: `उपकृष्णः`
(C4a) and `त्रिभुवनानि` (C7).

**Harness caveat for later stages.** The evaluator passes a `review` target on
anything short of 🔴, including silence and generic noise, so the
known-gap line (9/16) overstates the baseline — the real figure is 0/16. From
C2 on, a ⚪-target case only counts as caught if it raises a finding on
`expected_error_surface` whose reason is the stage's own rule.

**Caveat on the cases themselves.** The Sanskrit in `samasa.json` was written
for this plan and has not been reviewed by a second person. Treat a surprising
result on any case as a reason to re-check the case, not only the engine.

### 10.7 C1 results (2026-09-17) — gate failed

**Built** (read-only, changes nothing in the product):
- `tests/dcs_eval/c1_shape_check.py` — applies the shape check to every token
  the product leaves unrecognised at ⚪ on the Experiment-1 DCS sample.
- `tests/dcs_eval/c1_labels.json` — hand labels for all 71 accepts and a
  seeded (17) sample of 40 rejects. Labelled once, not second-reviewed.

**DCS gold was not usable.** The candidate file dropped DCS's multiword
ranges; recovering them from the `standalone` flag failed on 142/260
sentences and mis-aligned others (`तथोक्तम्` matched to `utpadyate`). The
alignment table the script prints is not to be trusted; the labels are.

**Correct text: 477 unrecognised tokens.**

| Shape verdict | Tokens |
|---|---|
| no split | 243 |
| non-final piece not a stem | 163 |
| **compound shape (accepted)** | **71 (14.9%)** |

| Hand label | Accepted (71) | Rejected sample (40) |
|---|---|---|
| split correct | 43 | 15 |
| split wrong | 25 | 25 |
| unsure | 3 | — |

- **Precision on accepts ≈ 63%** (43 of 68 decided).
- **Only 7 of the 43 correct accepts are real compounds** (`स्पन्दात्मके`,
  `इन्द्रियोत्पत्तौ`, `कारणान्तरस्य`, `बुद्ध्यादयः`, `यमकादिषु`,
  `पण्योपघाते`, `मेध्याभ्यवहरणादि`). The other 36 are sandhi-joined phrases
  (`तथापि`, `यश्च`, `चात्र`): an avyaya's prātipadika is spelled like the avyaya
  itself, so particles pass as compound members.
- Junk comes in two shapes: very short real pieces (`चित्तनिरोधे →
  cit+tan+iras+De`, `सत्त्वरजस्तमांसि → sat+tu+arajas+tamAm+si`) and `iti`/`api`
  read with a long vowel (`अस्तीति → asti+Iti`, `नापि → na+Api`).
- The 15 correct rejects are all ordinary phrases (`तुष्टस्तस्य`,
  `रोगाद्विमुच्यते`) — correctly not compounds, but correct Sanskrit.

**Misspelled text: Experiment 2, 100 multi-letter typos.** 13 already get 🔴
with a correction; 87 get ⚪. Of those 87, **6 (6.9%) pass the shape check**,
every one on a junk split (`स्थापयस् → sTA+Apayas`, `शोजैः → Sas+jEs`,
`वेषुः → vA+Izus`).

**What that means for C2.** Silencing shape-passing tokens would remove 71 of
477 ⚪ flags on correct text (14.9%) and silence 6 of 87 ⚪ typos (6.9%). The
check is only about twice as likely to pass a correct word as a misspelled
one, and on correct text it mostly recognises particle phrases, not compounds.
That does not meet "separates correct compounds from junk reliably". **C2 as
specified is not built.**

**Correction to §10.4.** C1's go/no-go note said every later stage depends on
the shape check. That overstated it:
- **C3** (case ending retained) does depend on splits; with 25 of 71 accepted
  splits wrong it cannot be 🔴 on this evidence, and needs its own precision
  measurement before anything ships.
- **C4, C5, C7** key off a visible first member (उप/प्रति…, महत्, a numeral) and
  do not need the general shape check. They remain buildable.
- **C6, C8** need the members identified, so they inherit C1's weakness.

Not tried, to avoid tuning on the data used to judge it: minimum piece length,
excluding long-vowel `Iti`/`Api` pieces, or a particle-phrase rule. Any of these
needs a held-out sample before it counts.

### 10.8 C4 results (2026-09-17) — shipped at ⚪

**What it does.** An *unrecognised* word that reads as an अव्ययीभाव head
(`AVYAYIBHAVA_HEADS`: यावत्, अन्तर्, बहिस्, प्रति, यथा, उप, अनु, अधि) plus a
declined form of exactly one kind of final member gets `status:
"samasa_error"`, severity ⚪, the compound's expected spelling as its
suggestion, and the sūtra that produces that spelling:

| Written | Suggested | Sūtra cited |
|---|---|---|
| `उपगङ्गाम्` | `उपगङ्गम्` | ह्रस्वो नपुंसके प्रातिपदिकस्य (१.२.४७) |
| `उपनद्याम्` | `उपनदि` | ह्रस्वो नपुंसके प्रातिपदिकस्य (१.२.४७) |
| `प्रतिदिनेषु` | `प्रतिदिनम्` | नाव्ययीभावादतोऽम्त्वपञ्चम्याः (२.४.८३) |
| `यथाशक्तिः`, `यथाविधिः` | `यथाशक्ति`, `यथाविधि` | अव्ययादाप्सुपः (२.४.८२) |

The optional -आत्/-एन/-ए forms of an अ-final member (२.४.८३, २.४.८४) are
accepted. If the member's readings disagree on the spelling, nothing is
offered. Only ordinary (Basic) प्रातिपदिकs are read: a कृदन्त entry's lemma is its
root, not its stem.

Also added: `_is_avyayibhava_luk_form` recognises यथा- + a bare इ/उ member
(`यथाशक्ति`, which drew ⚪ "not in lexicon" before). Limited to यथा- because a
bare इ/उ word under उप/अनु/प्रति is also what a dropped visarga looks like
(`अनुभूति` for `अनुभूतिः`), and recognition runs ahead of the spelling
corrector.

**The safety comes from one gate: never re-read a word the lexicon carries.**
Without it the rule would "correct" correct prādi nouns — `उपवनानि` →
`उपवनम्`, `उपकरणानि`, `उपमानानि`, `प्रतिबिम्बानि`, `प्रतिज्ञाम्` → `प्रतिज्ञम्`.
All of these, and all 37 prādi/other compounds sampled, are in the Kosha. The
same gate puts `उपकृष्णः` (S104-01) out of reach: the Kosha carries उपकृष्ण.

**Why ⚪ and not 🔴 for the vowel-shortening rule.** The plan's 🔴 gate is "fires
on no DCS sentence". Only 9 unrecognised DCS words start with a head at all,
and none splits into head + known member, so the rule had nothing to fire on —
passing that gate would have been vacuous, not evidence. The head alone also
does not prove the word is an अव्ययीभाव rather than an unlisted prādi compound.

**API.** `TokenResult.samasa_issue` / `TokenOut.samasa_issue` added (additive).
Frontend: `reviewReason` returns `'samasa'`; margin line "As an अव्ययीभाव
compound, expected …"; popover shows the full note, and keeps a samāsa note
visible as "Also" if a syntax error later takes over the token.

**Harness.** `evaluate_gold.py` honours an optional `expected_status`: a case
naming one passes only if that word carries that exact finding, so silence and
generic ⚪ no longer count. No main-gold case has the field.

**Measurements.**

| | Before | After |
|---|---|---|
| Gold | 139/155 | **byte-identical per test** |
| Samāsa set, in scope | 33/33 | **47/47** (42 correct + 5 wrong forms, strict status) |
| DCS false positives | 17/260 (6.5%) | 17/260 (6.5%) |
| DCS review-only / clean | 216 / 27 | 216 / 27 |
| Experiment 2 recall | 15/206 | 15/206, **per-case JSON identical** (A/B on the engine file) |
| Cold start | — | 1.63 s |

**Logged, not fixed (pre-existing, found while testing).** The visarga-sandhi
note suggests `सो गच्छति` / `एषो गच्छति`. Before a consonant सः and एषः drop
the visarga — `स गच्छति`, `एष गच्छति` (एतत्तदोः सुलोपोऽकोरनञ्समासे हलि
६.१.१३२). Before short अ, `सोऽपि` is correct and is suggested correctly. It is
a ⚪ note with a wrong suggestion; it needs its own cycle in
`app/sandhi_checker.py`. **Fixed — see §10.9.**

### 10.9 सः/एषः sandhi fix (2026-09-17)

Fixes the ⚪ note logged in §10.8. `SandhiChecker.check_junction` now applies
एतत्तदोः सुलोपोऽकोरनञ्समासे हलि (६.१.१३२) ahead of the general visarga rules.

| Written | Before | After |
|---|---|---|
| `सः गच्छति` | ⚪ suggest `सो` (हशि च) | ⚪ suggest **`स`** (६.१.१३२) |
| `एषः गच्छति` | ⚪ suggest `एषो` | ⚪ suggest **`एष`** |
| `सो गच्छति`, `एषो गच्छति` | silently accepted | ⚪ suggest `स` / `एष` |
| `स गच्छति`, `एष गच्छति`, `सोऽपि`, `यो`, `को`, `रामो` | — | unchanged |
| `सः पठति` (voiceless) | silent | **still silent** |

The sūtra also covers voiceless consonants, and the first version flagged
`सः पठति` too. That put a new ⚪ on gold 11-114 `सः संस्कृतं पठति।`, a case named
*must_not_flag*, and on 14-146 `सः तत् करोति।`. `सः` before a voiceless consonant
is the ordinary modern spelling, so the note is now raised only where one was
raised before (a voiced consonant) or where the written form is the wrong -ओ
one. Gold byte-identical after that change.

### 10.10 C5 results (2026-09-17) — 5a shipped at ⚪, 5b not built

**5a — महत् → महा (आन्महतः समानाधिकरणजातीययोः ६.३.४६), shipped ⚪.** An
*unrecognised* word written with any पदान्त spelling of महत् (`MAHAT_SPELLINGS`:
महत्/महद्/महन्/महच्/महज्/महल्) followed by a known ordinary word gets
`samasa_error` with महा- substituted, applying sandhi where the member begins
with a vowel:

| Written | Suggested |
|---|---|
| `महत्पुरुषः` | `महापुरुषः` |
| `महत्देवः`, `महद्देवः` | `महादेवः` |
| `महदीश्वरः` | `महेश्वरः` |

⚪ because the sūtra covers only a कर्मधारय or बहुव्रीहि; a षष्ठी-तत्पुरुष keeps
महत्- (`महत्सेवा`, "service of the great") and form alone cannot tell them
apart. Same lexicon gate as C4: every correct महत्- word sampled (`महत्सेवा`,
`महत्त्वम्`, `महत्तरः`, `महत्तमः`, `महद्भ्यः`) is in the Kosha and is never
re-read.

**5b — राजन्/सखि + टच् (राजाहस्सखिभ्यष्टच् ५.४.९१), not built.** The errors it
targets — `महाराजा`, `देवराजा`, `धर्मराजा`, `कृष्णसखा` — are all *in the lexicon*,
because each is the correct spelling of a बहुव्रीहि ("one who has a great
king"); टच् applies to तत्पुरुष only. The rule could only fire by overriding a
lexicon hit, the one gate that keeps C4 and 5a off correct words. Without that
gate the prototype also mis-parsed `महाराज्ञी` ("great queen"). This is the
"compound type is not visible in the form" limit of §10.2, now measured.

Frontend margin line for `samasa_error` is now rule-neutral ("Compound form:
possibly …"), since two rules share the status.

**Measurements (after the सः fix and 5a together).**

| | Before | After |
|---|---|---|
| Gold | 139/155 | **byte-identical per test** |
| Samāsa set, in scope | 47/47 | **54/54** (45 correct, 9 wrong forms with strict status) |
| DCS false positives | 17/260 (6.5%) | 17/260 (6.5%) |
| DCS review-only / clean | 216 / 27 | 216 / 27 |
| Experiment 2 recall | 15/206 | 15/206, per-case JSON identical |

DCS offered 2 candidate words for C5 (महत्-, -राज-, -सख-), neither a hit, so —
as with C4 — DCS is no evidence either way.

### 10.11 C6–C8 results (2026-09-17) — none built; samāsa plan closed

Each was prototyped and measured before any engine code, on its test-set wrong
forms, hand-built correct look-alikes, and the 477 unrecognised words of the
Experiment-1 DCS sample (all correct Sanskrit, so every fire there is a false
note). Prototype: an unrecognised word only, the same lexicon gate as C4/C5a.

| Stage | Wrong forms caught | Fires on correct DCS words | Verdict |
|---|---|---|---|
| C6 last-member gender (२.४.२६) | 3 of 4 (`राजकन्यः`, `नृपकन्यः`, `गुरुभार्यः`) | **41** | not built |
| C7 collective द्विगु singular (२.४.१) | 1 of 4 reachable | 0 | not built |
| C8 द्वन्द्व number | — | **7** | not built |

**C6.** A masculine compound whose last member has a feminine homograph stem is
spelled exactly like the error: `षोडशगुणः` (गुणा), `सुखदुःखयोगः` (योगा),
`गोचर्यः`. Restricting to endings a feminine आ-stem can never take still left
41 false notes against 3 real catches. Among recognised words the same shape
covers names and बहुव्रीहिs (`वीरसेनः`, `भीमसेनः`, `सत्यकामः`, `चन्द्रगुप्तः`),
which only the lexicon gate kept quiet.

**C7.** Three of the four target forms — `त्रिभुवनानि`, `पञ्चपात्राणि`,
`त्रिलोकाः` — are lexicon hits, so under §10's gate they are unreachable. The
remaining shape (numeral + plural) is also a correct बहुव्रीहि plural
(`पञ्चमुखाः`, `त्रिनेत्राः`), so even the one reachable form cannot be flagged
on form alone.

**C8.** Every singular two-stem compound is either a द्वन्द्व written in the
wrong number or an ordinary तत्पुरुष, and the spelling is identical. The
prototype fired on `सङ्गदोषः`, `नियोगपर्यायः`, `विकरणभावः`, `सदृशरूपः` — all
correct तत्पुरुष — and on no real error. vidyut has no proper-noun tag (§4.10),
so "two names" cannot be used to narrow it.

The wrong forms stay in `tests/gold/samasa.json` as permanent known gaps, each
with the reason in its note.

**Where the samāsa plan ends up.**

| Stage | Outcome |
|---|---|
| C0 | Test set (65 cases) + harness `--dataset` / `expected_status` |
| C1 | Shape check measured; gate failed |
| C2 | Not built (depends on C1) |
| C3 | Not built (depends on splits; C1 showed 25 of 71 accepted splits wrong) |
| C4 | **Shipped ⚪** — अव्ययीभाव endings (१.२.४७, २.४.८२, २.४.८३) |
| C5a | **Shipped ⚪** — महत् → महा (६.३.४६) |
| C5b | Not built — targets are correct बहुव्रीहि spellings in the lexicon |
| C6, C7, C8 | Not built — measured above |

Also fixed along the way: the पितरौ नमामि false 🔴 (§10.6) and the सः/एषः sandhi
suggestion (§10.9).

The common cause behind every "not built": **compound type is not visible in
the spelling.** The rules that shipped are the ones whose wrong form is wrong
under *every* type (an indeclinable with a case ending; महत्- where no
षष्ठी reading is involved is left to review). Everything else needs either
meaning or a real segmenter with calibrated confidence — the latter still
parked as a one-off offline TransLIST harvest (§10.1).

**Open follow-up (found in §10.10 testing, not fixed).** The spelling corrector
runs before the samāsa checks, so it can pre-empt them: `अनुगङ्गाम्` gets a 🔴
"spelling correction" to the right answer under the wrong label, and
`प्रतिमासाः` gets a **wrong 🔴** (`प्रतिमांसाः`). Reordering needs gold and
typo-recall measurement, because it could also hide real typos. **Fixed — see §10.12.**

### 10.12 Samāsa check ahead of the spelling corrector (2026-09-17)

Closes the follow-up in §10.11. `check_word` now returns "unrecognised, no
suggestion" for a word that reads as a samāsa written against a C4/C5a rule,
beside the existing `_is_productively_composite` gate and before any
edit-distance correction. `check_text` then raises the ⚪ samāsa note.

| Word | Before | After |
|---|---|---|
| `प्रतिमासाः` | **🔴 "spelling" → प्रतिमांसाः (wrong word)** | ⚪ samāsa → `प्रतिमासम्` (२.४.८३) |
| `प्रतिक्षणाः` | 🔴 "spelling" → प्रतीक्षणाः | ⚪ samāsa → `प्रतिक्षणम्` (२.४.८३) |
| `अनुगङ्गाम्`, `अनुवेलाम्` | 🔴 "spelling" → right form, wrong label | ⚪ samāsa → `अनुगङ्गम्`, `अनुवेलम्` (१.२.४७) |

**A 5a flaw surfaced by the measurement, and fixed.** The Experiment-2 A/B
changed one case: `महदादि` ("Mahat and the rest", in an uncorrupted part of a
DCS sentence) lost a false 🔴 (`महदाद्`) but gained a ⚪ proposing `महादि`.
६.३.४६ needs महत् to describe the other member, and in an "X and the rest"
compound X is the thing listed. `LISTING_FINAL_MEMBERS` (आदि, आद्य, प्रभृति,
प्रमुख) now blocks 5a, and `_is_mahat_listing_compound` keeps such words away
from the edit-distance corrector too, so `महदादि` is now a plain ⚪ unrecognised
word with no suggestion.

**Measurements.**

| | Before | After |
|---|---|---|
| Gold | 139/155 | **byte-identical per test** |
| Samāsa set, in scope | 54/54 | **57/57** (11 wrong forms with strict status) |
| DCS Exp. 1 | 17 FP / 216 / 27 | identical, per-sentence JSON identical |
| DCS Exp. 2 recall | 15/206 | 15/206; **1 case changed** — the false 🔴 on `महदादि` removed, no typo lost |
| samāsa notes on correct DCS text (Exp. 1 + Exp. 2 originals, 466 sentences) | — | **0** |

### 10.13 Pada-final -र् and anusvāra-before-vowel (2026-09-17)

Both found by running the first real-text sample
(`tests/real_text/sample_01_rama.txt`, 138 words, supplied as correct).

**-र् mistaken for -स्.** A पदान्त visarga can stand for either, and the junction
code assumed -स् throughout, so पुनः and प्रातः were offered as पुनो and प्रातो.
`SanskritEngine._repha_base` now rewrites the base to -र् when the Kosha reads
the -र् spelling as an **अव्यय** — पुनर्, प्रातर्, अन्तर् have such a reading and
पुनस्/प्रातस्/अन्तस् do not. vidyut's own rules.csv then produces the junction;
it carries no sūtra for these, so `check_junction` cites them:

| Written | Suggested | Sūtra |
|---|---|---|
| `पुनः गुरोः` | `पुनर्गुरोः` | खरवसानयोर्विसर्जनीयः (८.३.१५) |
| `पुनः अपि` | `पुनरपि` | ८.३.१५ |
| `प्रातः रामः` | `प्राता रामः` | रो रि (८.३.१४) / ढ्रलोपे पूर्वस्य दीर्घोऽणः (६.३.१११) |
| `पुनः च` | `पुनश्च` | विसर्जनीयस्य सः (८.३.३४) / स्तोः श्चुना श्चुः (८.४.४०) |
| `पुनः पठति` | — correct as written | |

The अव्यय test is what keeps this off the *other* -र् class: गुरोः + voiced is
also गुरोर् (सस्जुषो रुः ८.२.६६), but that -र् arises by sandhi rather than being
lexical. Junctions of that kind are still silent — a separate gap, not touched.
The ऋ-stem vocative (पितः → पितर्) is likewise not covered: it has no अव्यय
reading.

**Anusvāra before a vowel.** मोऽनुस्वारः (८.३.२३) replaces a पदान्त म् with
अनुस्वार only before a consonant, so `शीघ्रं उत्तिष्ठति` should be `शीघ्रम्
उत्तिष्ठति`. Decided by spelling alone — a final anusvāra, a vowel next — and
raised as ⚪ in the same `elif` as the sandhi note, so it never displaces one.

**New regression set.** `scripts/build_sandhi_dataset.py` →
`tests/gold/sandhi.json`, 20 cases over §10.9's सः/एषः rule and both of the
above, scored by `evaluate_gold.py --dataset`. Wrong forms carry
`expected_status`, so silence does not pass.

**Measurements.**

| | Before | After |
|---|---|---|
| Gold | 139/155 | **byte-identical per test** |
| Samāsa set | 57/57 | 57/57 |
| Sandhi set | — | **19/20** (the one failure is a pre-existing defect, below) |
| DCS Exp. 1 | 17 FP / 216 / 27 | **0 of 260 cases changed** |
| DCS Exp. 2 | 15/206 | **0 of 206 cases changed** |
| Real sample | 0 🔴, 16 ⚪ | 0 🔴, 19 ⚪ (3 anusvāra added; 2 wrong suggestions corrected) |

DCS is entirely unaffected because it is printed sandhi-joined; both advisories
only speak to text that writes words apart, which is what the real sample does.

**Found by the new set, not fixed: a 🔴 on correct text.** `जलं पिबन्ति।` ("they
drink water") is asserted as a subject-verb number error, because neuter जलम्
is spelled the same in प्रथमा and द्वितीया and is taken as the subject of a
plural verb. `ते जलं पिबन्ति।` is clean. This is the same syncretism as the
पितरौ नमामि defect (§10.6) but with a प्रथम-पुरुष verb, which that fix does not
cover. `D203-04` is deliberately left **failing in scope** rather than recorded
as a known gap, since it is a false assertion. **Fixed — see §10.14.** A fix would need the object
reading to be admissible only where the verb can take an object
(`TRANSITIVE_DHATU_MAP`), so that `फलानि पतति` keeps its error.

### 10.14 जलं पिबन्ति — the प्रथम-पुरुष half of the syncretism defect (2026-09-17)

Closes the failing case left in §10.13. `जलं पिबन्ति।` ("they drink water") was
asserted 🔴 as a number error: neuter जलम् is spelled alike in प्रथमा and
द्वितीया, so it was taken for a singular subject of a plural verb. The §10.6 fix
did not reach it — that one keys on the verb being उत्तम/मध्यम, and here the verb
is प्रथम, the same person a nominal subject carries.

**Shipped condition.** The object reading is allowed against a प्रथम-पुरुष verb
only when *both* hold:
- the subject is **neuter**, where प्रथमा and द्वितीया coincide by rule
  (स्वमोर्नपुंसकात् ७.१.२३), and
- the verb can take an object (`TRANSITIVE_DHATU_MAP`).

**The first condition was learned by measurement.** Reusing the general
syncretism test cost **five gold cases** (139 → 134): `बालकाः` is also the
द्वितीया बहुवचन of the feminine बालका, so an unrelated reading excused the real
error in `बालकाः पठति`. A dual in -औ is syncretic too, but gold 3-35
(`बालकौ पठति`) requires that to stay an error, so the licence stops at neuter.
The उत्तम/मध्यम branch keeps the wider test, because there *no* nominal can be
the subject at all, which is a stronger licence than "some reading exists".

| Sentence | Before | After |
|---|---|---|
| `जलं पिबन्ति।`, `फलानि खादति।` | 🔴 | clean |
| `फलानि पतति।` (पत् takes no object) | 🔴 | 🔴 |
| `बालकाः पठति।`, `बालकौ पठति।`, `रामाः पठति।` | 🔴 | 🔴 |
| `बालकाः पुस्तकं पठति।`, `बालकाः पठति च।` | 🔴 | 🔴 |

**Measurements.**

| | Result |
|---|---|
| Gold | **byte-identical per test** (139/155) |
| Sandhi set | **20/20** (was 19/20) |
| Samāsa set | 57/57 |
| DCS Exp. 1 / Exp. 2 | **0 of 260 and 0 of 206 cases changed** |
| Real sample | 0 🔴, 19 ⚪ — unchanged |

**Known limit.** The licence rests on `TRANSITIVE_DHATU_MAP`, a hand-written
list of 14 roots. A neuter subject with a transitive verb outside that list
still draws the 🔴 — the failure mode is a false assertion, not a miss, so the
list is the next thing to widen if this recurs on real text.

---

# Appendix — defect-round history

The sections below are the working record of the four defect rounds and the
harness fix that followed the phase's first close. They are kept because they
contain the measurements behind several entries in the gap catalogue.

**Note on numbering.** These sections predate the restructure above and are
prefixed `A`. A few of their internal references (`§2`, `§4`, `§4.1`, `§4.2`)
use the *round-era* numbering, in which §4 was the three-category gap list;
those now correspond to the gap catalogue at §4 and the tier table at §2.

## A8. Post-close defect round (2026-09-06)

Five defects were reported from testing after the phase was first closed. All
five are resolved; both eval sets were re-run after each fix, not only at the
end.

| # | defect | cause | fix |
|---|---|---|---|
| 1 | **एकस्मिन् → कस्मिन्** (and एकस्मै → कस्मै, एकस्मात् → कस्मात्) | The spelling corrector reached a real word by deleting the token's **first** letter. A4's veto covers sandhi fusions only, so nothing stopped it. | Word-initial deletion is no longer a correction candidate, generalising the existing नञ् guard. Word-initial material in Sanskrit is morphologically load-bearing — a नञ्, an उपसर्ग, or the stem itself. Verified free: every genuine typo the gold set catches edits at position ≥ 1. |
| 2 | **ग्रामे read as "Prathama, Dvi vacana" and selected as subject** | Phase C *demoted* this to review but still generated it. A locative adjunct with an elided subject has no subject-verb relation to have an opinion about. | A token whose number the analysis does not settle is no longer a subject *candidate*; the finder skips it and keeps looking. A second pass added dropped-visarga restoration, since नरा/प्रतिलोमा stand for नराः/प्रतिलोमाः and were being read as singulars. |
| 3 | **इत्युक्त्वा → इत्युक्ता** | Cheda splits it correctly (इति + उक्त्वा), but the veto's function-word test did not recognise उक्त्वा. The यण् in इत्युक्त्वा is *medial*, so the A2 padānta ladder never applied — correctly, since that ladder is word-final by design. | The अव्ययकृत् rule (क्त्वा/ल्यप्/तुमुन्, १.१.४० and १.१.३९) already used by the syntax layer is now shared with the engine's function-word test. Fixes इत्युक्त्वा, इत्येवम्, इत्याह, इत्युच्यते. |
| 4 | **न → नो, citing हशि च (६.१.११४)** | The bare-stem restoration promoted any `-a`-final token to `-as` when `nas` happened to exist in the Kosha. न is an अव्यय with no case ending to restore. | The promotion now skips अव्ययs. राम → रामो and रामः → रामो still work. |
| 5 | **तथापि and गुरुशिष्यपरम्परा shown as errors** | **Backend was correct** — both are `status="invalid", severity="review"`. The live UI (`sanskrit-checker-frontend/src/App.jsx`) branched on `status` only and never read `severity`, so it rendered every unrecognized word as "अशुद्धं पदम्". | UI now honours severity: a neutral slate ⚪ review tier, distinct wording that states the finding is *not* an error, and a separate "for review" count. `review_count` added to the API response. |

**Coverage gaps closed.** Neither the bare "locative + verb, no nominative"
pattern nor any सर्वादि oblique of एक was tested by either eval set —
ग्रामे appeared in the gold data only as a gloss on a compound case, never as
an input. Seven regression cases were added (`tests/gold/dataset.json`,
section 15), taking the gold set from 150 to 157.

**Net effect of the round:** DCS false positives **8.1% → 6.9%**, fully-clean
sentences 10.4% → 11.2%, review rate 81.5% → 81.9%, gold error recall
unchanged at 40/57, FP-avoidance and review-correctness at 100% on the larger
set (47/47, 37/37).

**On the frequency-weighted disambiguation that was requested for #1:** it was
not implemented, and deliberately. The only Sanskrit corpus available offline
here is the DCS pool — which is exactly what Experiment 1 and Experiment 2 are
drawn from. Deriving correction frequencies from it would leak the evaluation
set into the engine and make every subsequent number unreliable. The
positional rule shipped instead is Vidyut-native, needs no corpus, was
verified to cost nothing in recall, and fixes the whole एक family rather than
the three reported forms. If frequency weighting is still wanted later, it
needs a corpus fetched separately from both experiment pools.

---

## A9. Second defect round (2026-09-06)

| # | defect | verdict | fix |
|---|---|---|---|
| 1 | **तस्य पुत्रः कन्या च वर्तेते** asserted as a 🔴 agreement error, suggesting वर्तते | **Real 🔴-tier violation.** Two coordinated singulars take a dual verb, so the sentence is correct and the suggestion would have corrupted it. | A local pattern test: a coordinating particle (च, वा, अथवा, किंच) among two or more prathamā-capable nominals before the verb suppresses the subject-verb check. Requires **both** the particle and ≥2 nominals, so an unrelated च in a single-subject sentence (बालकाः पठति च) still lets a genuine error fire. No dependency parsing involved. |
| 2 | **प्रतिदिनम् unrecognized** | **Neither** a systematic upasarga gap nor the compound ceiling. Of 16 अव्ययीभाव adverbials sampled, the Kosha carries 11 (प्रत्यहम्, प्रतिवर्षम्, प्रतिक्षणम्, अनुदिनम्, उपकूलम्, प्रत्येकम् …) and lacks 5. These are individual lexical holes in a finite list — the same category as the `-तस्` adverbs in §4.1. | vidyut 0.4.0 has **no समास support at all** (`Samasa` is absent from `prakriya`), so these cannot be derived. Recognition instead checks the structure: an उपसर्ग/अव्यय prefix plus an independently recognised remainder ending in **-अम्** (नाव्ययीभावादतोऽम्त्वपञ्चम्याः, २.४.८३). The -अम् condition is what makes it safe — it excludes उपसर्ग-prefixed *verbs* (परिमुच्यते, परिक्षरति) and excludes परिक्षा, which a bare prefix-strip would have validated as परि + क्षा. Verified against every gold-set typo: none is validated. |
| 3 | **भवति shown as "Stem/Root: भवत्"** | **Display only — the derivation is correct.** VerbGrammar derives भवति from भू (codes 01.0001, 10.0382) and the syntax layer always read it as a verb. The Kosha also carries भवत् (the honorific / शतृ participle) whose Saptamī singular is spelled identically, and `_pick_best_entry`'s preference for an ordinary Basic stem handed the *label* to that. The sūtra-citable path was never wrong. | A finite verb now outranks a nominal homograph for display, restricted to a Prathama-puruṣa reading so genuine nouns keep their identity (भावः matches an उत्तम dual of भा and stays the noun भाव). Fixing this exposed a second display defect: roots were shown in raw Dhātupāṭha citation form (`ग॒मॢँ`, `डुकृ॒ञ्`). The Kosha's own `DhatuEntry.clean_text` now supplies the display root — गम्, कृ, पठ्, वृत् — rather than stripping anubandhas by hand. |

The coordination test was extended to the liṅga check as well, since coordinate
enumerations were two of the four remaining false positives there. It resolved
`गलः / पृष्ठं` (…जघनम् ऊरू **च** स्थानानि), which carries an explicit
coordinator. `दण्डः / शुल्कं` has none and remains a parser case.

**Twelve regression cases added** across both rounds (gold set 150 → 162):
locative adjuncts with elided subjects, सर्वादि obliques of एक, coordinated
dual subjects, and an agreement error accompanied by an unrelated च.

**Net effect:** DCS false positives **6.9% → 6.5%**, syntax-level error flags
4 → 3, fully-clean sentences 11.2% → 11.5%, gold error recall 40/57 → **41/58**,
with FP-avoidance and review-correctness at 100% on the larger set.

## A10. Third defect round (2026-09-06) — two 🔴-tier violations

Both reported defects were real, both were 🔴-tier assertions against correct
Sanskrit, and both were **category 1**: the information needed to avoid them
was already in vidyut's own data and was simply not being consulted
symmetrically. No new heuristic, no external evidence, no parser.

### A10.1 भरतः taken for the clause's verb

`रामः लक्ष्मणः भरतः च गच्छन्ति` was flagged 🔴 "Subject 'रामः' is Eka but the
verb 'भरतः' is Dvi". भरतः is a proper noun *and* a well-formed प्रथम-द्विवचन
of भृ, so the syntax layer took it for the verb and ignored the real verb
गच्छन्ति.

**The reported cause was not the actual cause.** The round-2 भवति display fix
was suspected of driving this. It is not: `verb_readings` is populated in
`check_text` directly from `VerbGrammar.lookup`, independently of
`check_word`, and the verb-candidate test is satisfied by `verb_readings`
alone before the analysis string is ever consulted. The display fix is
genuinely display-only, as round 2 reported. The actual cause is older and
sits in the verb-candidate filter itself: the पुरुष filter rules out spurious
उत्तम/मध्यम readings **by sūtra** (१.४.१०७, १.४.१०५ make those puruṣas
conditional on अस्मद्/युष्मद् being present), but no sūtra rules out a
spurious *प्रथम* reading — and प्रथम is exactly where the damaging collisions
sit.

**The prescribed fix is not implementable: vidyut has no proper-noun tag.**
`PratipadikaEntry` has exactly two variants, `Basic` and `Krdanta`; there is no
नामविशेष / संज्ञा field anywhere on `PadaEntry` or `PratipadikaEntry` in
0.4.0. Ranking proper nouns above verb homographs cannot be done, and inferring
proper-noun status from a stem list would be exactly the kind of unmeasurable
heuristic this project has twice reverted.

The broader alternative was implementable, and is what was built: **an
ambiguous verb candidate yields to an unambiguous one.** A genuine तिङन्त's
only nominal homographs are कृदन्त forms of its own root — गच्छति, पठति and
गच्छन्ति have `Krdanta` entries only — whereas a noun that collides with a
paradigm cell has a `Basic` प्रातिपदिक entry of its own. So when a sentence
contains a verb candidate with no independent nominal identity, the candidates
that *do* have one are not the verb.

The rule fires only when an unambiguous candidate exists, which is what keeps
it from regressing the round-2 work: अस्ति and भवति both carry Basic प्रथमा
readings and, being the only candidate in their sentences, keep their verb
status. In a two-clause sentence the rule can cost a detection; it can never
manufacture an assertion — the ordering this project requires.

### A10.2 Subject-finder falling through an unrecognized token

`रामलक्ष्मणौ वनं गच्छतः` was flagged 🔴 against the correct dual गच्छतः. The
unsegmentable द्वन्द्व रामलक्ष्मणौ is correctly flagged ⚪, but the subject
search then continued past it and settled on वनं — whose neuter प्रथमा and
द्वितीया are identical — and read the accusative object as the subject.

The finder had one behaviour for two opposite states. An अव्यय is
*grammatically disqualified*, so continuing past it is right and lets a real
subject later in the clause still be found. An **unrecognized** token is not
disqualified — nothing is known about it, and it may well be the कर्ता — so
continuing past it silently promotes the next nominal into a role it may not
hold. The finder now abandons the subject-verb check when it passes over an
unrecognized token, rather than redirecting to its neighbour.

The abandon test sits *after* the surface-ending fallback, so a token that
fallback legitimately claims (महामोहावृतमनाः, a -मनस् compound recognised by
its -आः ending) is unaffected.

### A10.3 Logged, not fixed: participle liṅga agreement is uncovered

`बालिका पठन् अस्ति` produces no flag. This is a **missed detection, not a
wrong assertion**, so it ranks below the two above by the project's standing
severity ordering. It is a distinct gap from the compound-segmentation ceiling
(§4.2) and the सर्वादि library gap (§4.1), and it has **two independent
causes**, measured:

1. **The masculine शतृ nominative is excluded outright by an ending guard.**
   `_prathama_lingas` only accepts tokens ending in `H / m / M / A / I`, a
   guard added so that a bare unsandhied compound stem is not read as a
   standalone nominative. The masculine शतृ प्रथमा-एकवचन ends in **-न्**
   (पठन्, गच्छन्), which that guard was never designed to cover, so पठन्
   returns *no* liṅga at all and the pair is never tested. This part is
   **category 1** — narrow and testable — but it widens an ending guard whose
   whole purpose is false-positive suppression, so it needs its own
   measurement cycle rather than being appended to this round.
2. **Where a participle is reachable, it is often genuinely ambiguous.** The
   feminine पठन्ती is Stri/प्रथमा/एक *and* Napumsaka/प्रथमा/द्वि at top rank,
   so the existing ambiguity gate correctly declines to assert. This part is
   not fixable by widening anything; it is real morphological syncretism.

### A10.4 Measurement

Every number below is unchanged from round 2. Both fixes are narrow enough
that neither defect's pattern occurs in the 260-sentence DCS sample — both
were constructed cases — so the value here is the **absence of movement**:
no regression on either set, and the three remaining syntax false positives
are still exactly the three parser cases documented in §4.2.

| metric | round 2 | **round 3** |
|---|---|---|
| Gold in-scope pass rate | 129/146 | **134/151 (88.7%)** (5 new guards) |
| Gold error recall | 41/58 | **42/59 (71.2%)** |
| Gold FP-avoidance | 51/51 | **54/54 (100%)** |
| Gold review-correctness | 37/37 | **38/38 (100%)** |
| DCS Exp-1 false-positive rate | 6.5% | **6.5% (17/260)** |
| — syntax-level error flags | 3 | **3** |
| — token-level error flags | 14 | **14** |
| Review-only rate | 81.9% | **81.9%** |
| Fully clean | 11.5% | **11.5%** |
| Unrecognized-token rate | 30.4% | **30.4%** |
| Exp-2 overall recall | 15/206 | **15/206 (7.3%)** |

Verified directly: `रामः लक्ष्मणः भरतः च गच्छन्ति` → no flag; `रामलक्ष्मणौ वनं
गच्छतः` → no agreement flag, रामलक्ष्मणौ still ⚪ review-tier only. Controls
held: `भवति` → भू, `भावः` → भाव, `बालकाः पठति` → still flagged, `बालकाः पठति
च` → still flagged, `सुन्दरः बालिका अस्ति` → liṅga error still fires, and all
five section-16 coordination cases still pass.

**Five regression cases added** (gold set 162 → 167, new section 17): the
proper-noun/verb homograph, the sole-verb-candidate homograph, the
unrecognized-subject suppression, an ordinary recognized-subject control, and
a genuine agreement error with an accusative object present — the last of
these confirming the suppression cannot silence a real error. That case is
also a **new detection**, which is why gold error recall moves 41/58 → 42/59
while the DCS numbers stay flat.

## A11. Fourth defect round (2026-09-06) — the -आः vacana guess

### A11.1 Correction to the report: this was ⚪, not 🔴

The defect is real and the analysis of it was right, but its tier was not.
`महामोहावृतमनाः सः अस्ति` returns `error_count = 0`; the finding is emitted at
**review** severity, because the PHASE_C guard "`pronoun_hit is None and not
subj_tok.nominal_entries` → ambiguous → review" already covered it.

That does not make it harmless. A ⚪ finding titled **"Subject-Verb Agreement
Error"** that names a specific replacement — सन्ति — is asserting a rule
violation in everything but the colour of its badge, and applying it would
corrupt a correct sentence. §2 says the review tier is "never implied to be a
rule violation"; a concrete correction breaks that. So it was fixed, and the
correct description of the round is *a review-tier flag doing an error-tier
thing*, one severity class below the previous two rounds.

### A11.2 The grammar

-आः is nominative **plural** for an ordinary अ-stem (रामाः, बालकाः) and
nominative **singular** for an अस्-stem बहुव्रीहि (सुमनाः, महामोहावृतमनाः —
"one whose मनस् is enveloped by great delusion"). The subject-finder's
surface-ending fallback read the ending alone and assigned plural, then
reported the correct singular अस्ति as a number mismatch.

### A11.3 Option 1 was tried and measured, and does not work

Detecting the अस्-stem class directly *is* expressible against vidyut — the
discriminator is the **prātipadika** text, not the pada: for मनाः the stem
`manas` is itself an as-final Basic prātipadika, whereas for रामाः the
underlying `rAmas` is a *pada* whose stem is `rAma` and does not end in -as.
That test is exact for a bare word.

It fails for the case that matters, because the word is an **unsegmentable
compound** and nothing says where its final member begins. Scanning the token
for any suffix that forms a known as-stem was measured against the 23
recognised -आः forms in the DCS sample, where the Kosha supplies ground truth:

| variant | correct | wrong | fires on महामोहावृतमनाः? |
|---|---|---|---|
| suffix scan | 17/23 | **6/23 (26%)** | yes — but matches the junk substring `amanas` |
| + require the preceding material to be a recognised word | 20/23 | **3/23 (13%)** | **no** — its prefix महामोहावृत is itself an unsegmentable compound |

Every error is in the same direction: a genuine **plural** called singular
(सिराः → `iras`, पुरुषाः → `uzas`, प्रत्ययाः → `ayas`, कतमाः → `atamas`,
निरञ्जनाः → `janas`, आभ्यन्तराः → `taras`). The refinement that halves the
error rate also stops firing on the one word it was built for. There is no
signal to read here — the same "no signal available" finding as A1/A3 — so
**option 1 was rejected on measurement**, not on preference.

### A11.4 Option 2, as shipped

The surface-ending fallback is split by the evidence it rests on. An analysis
string that says प्रथमा came from a real derivation and is still usable. A
bare *ending* on a word the lexicon never confirmed is a guess about a stem
class that cannot be checked, so it no longer selects a subject — the token
falls through to §A10.2's unrecognised-subject rule and the check is abandoned.

Recognised subjects are untouched, which is the whole point: बालकाः, रामाः
and every other confirmed -आः plural keeps its 🔴, because for those the Kosha
states the vacana rather than the ending implying it.

### A11.5 Measurement

| metric | round 3 | **round 4** |
|---|---|---|
| Gold in-scope pass rate | 134/151 | **138/155 (89.0%)** |
| Gold error recall | 42/59 | **44/61 (72.1%)** |
| Gold FP-avoidance | 54/54 | **55/55 (100%)** |
| Gold review-correctness | 38/38 | **39/39 (100%)** |
| DCS Exp-1 false-positive rate | 6.5% | **6.5% (17/260)** |
| — error-severity syntax issues | 3 | **3** |
| — **review-severity syntax issues** | 8 | **7** |
| Review-only · fully clean | 81.9% · 11.5% | **81.9% · 11.5%** |
| Exp-2 overall | 15/206 | **15/206 (7.3%)** |

The single removed review-tier finding is exactly the one that carried a
corrupting `suggested_text`; all 7 that remain are liṅga-agreement findings
with `suggested_text = None`, which offer an observation rather than a fix.

**Four regression cases added** (gold set 167 → 171, section 18): the अस्-stem
बहुव्रीहि with an unrecognised compound, a *recognised* अस्-stem singular
(सुमनाः गच्छति), and two recognised अ-stem plural controls (रामाः पठति,
बालकाः गच्छति) that must keep firing. Gold error recall rises 42/59 → 44/61
because the two controls are genuine detections.

**A measurement caveat, now fixed — see §12.** `run_exp1.py` serialised only
error-severity syntax issues, so review-tier syntax counts could not be read
from `experiment1_sample.json`; the 8 → 7 above was measured by running the
engine over the corpus directly. The harness has since been corrected and
independently reproduces it.

## A12. Harness aggregation fix and re-derivation (2026-09-06)

### A12.1 The gap

`run_exp1.py` computed `review_issues` and used it for `has_review`, then
never wrote it out. The findings were not lost — the tokens they attach to
appeared in `review_tokens` with `status = agreement_error` and full analysis
strings — but no field held the findings themselves, so the file could not
answer "how many review-severity syntax issues are there?" and returned 0 to
anyone who asked it that way. A pure re-aggregation gap, not data loss.

`run_exp2.py` had the mirror defect: it serialised *every* syntax issue but
recorded no `severity`, so error and review findings were indistinguishable in
the file. Its recall numbers were always computed from a correctly filtered
set, so no reported figure was affected.

### A12.2 The fix

- `run_exp1.py` now writes a separate **`review_syntax_issues`** array, plus
  `syntax_issues_error` / `syntax_issues_review` in the summary and a line in
  the printed output. Kept **separate** from `syntax_issues` rather than
  merged into it, because `syntax_issues` is what defines
  `is_false_positive`, and every false-positive rate on record was computed
  with it error-only. Merging would have silently redefined the headline
  metric of the entire project.
- `run_exp2.py` now records `severity` on each serialised issue.
- Both files also carry `severity` on the error-tier entries, so no consumer
  has to infer it from which array a finding sits in.

### A12.3 Re-derived counts, corrected aggregation

Each round's code state was reconstructed by reverting that round's edits in
`karaka_syntax.py` and re-running the corrected harness:

| state | FP rate | syntax error-severity | **syntax review-severity** | review-only | fully clean |
|---|---|---|---|---|---|
| end of round 2 | 6.5% (17/260) | 3 | **8** | 213 | 30 |
| end of round 3 | 6.5% (17/260) | 3 | **8** | 213 | 30 |
| end of round 4 | 6.5% (17/260) | 3 | **7** | 213 | 30 |

### A12.4 Does any past claim change? No.

Checked explicitly, since that was the point of the exercise:

- **Round 3 (§A10.4) claimed "no regression on either set."** It listed
  syntax-level *error* flags (3 → 3), token-level error flags, review-only
  rate and fully-clean rate — none of which the gap could touch, because the
  gap only ever hid *review*-severity syntax findings. On the metric it never
  reported, the corrected aggregation gives **8 → 8**: still no regression.
  The claim holds, and is now verified on a metric it was not verified on
  before.
- **Round 4 (§A11.5) claimed review-severity syntax issues 8 → 7.** That was
  measured directly against the engine rather than from the JSON, precisely
  because the gap was known by then. The corrected harness reproduces **8 → 7**
  independently.
- **Rounds 2 and earlier** reported syntax counts at error severity only
  (§A8: "syntax-level error flags 4 → 3"), which the gap does not affect.

So the undercount never propagated into a reported number: every figure on
record was either error-severity, or measured outside the harness. The 7 findings
it was hiding are the 7 liṅga-agreement observations listed in
§A12.5 — all with `suggested_text = None`.

### A12.5 What the hidden findings actually were

All 7 are liṅga-agreement observations, none carrying a suggested correction:
कार्यः/पिण्डं, भावना/कर्तव्या, प्रतिभासा/प्रतीतिः, मृदा/लिप्तं,
अविद्या/क्षेत्रम्, विकृत्या/विनिमित्तं, विनिमित्तं/यः. They are review-tier
for the right reason — each rests on a morphological analysis that offers more
than one reading — and they are the residue §4 describes rather than a new
defect class.
