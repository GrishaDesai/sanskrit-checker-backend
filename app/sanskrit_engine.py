"""
Sanskrit validity-checking, orthographic correction, sandhi-verification,
and syntactic Kāraka/Agreement analysis engine.

Wraps vidyut's segmenter (Chedaka), lexicon (Kosha), supplemental lexicon,
spelling corrector, Paninian sandhi rules, and Karaka/Syntax engine to:
  1. Strip dandas/punctuation and accurately isolate Sanskrit word tokens.
  2. Check token-level validity against standard and supplemental lexicons.
  3. Detect common orthographic/typing errors (e.g. विध्यार्थी -> विद्यार्थी).
  4. Verify external sandhi (word-junction) between adjacent tokens.
  5. Check sentence-level Kāraka dependencies and verb government (e.g. भक्तानाम् -> भक्तान् रक्षति).
  6. Check Subject-Verb agreement (e.g. अहम् पठामि, बालकाः पठन्ति).
  7. Identify and decompose Sanskrit compounds (Samāsa analysis).
"""

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Optional

from vidyut.cheda import Chedaka
from vidyut.kosha import Kosha
from vidyut.lipi import Scheme, transliterate

from app.lexicon import SupplementalLexicon
from app.sandhi_checker import SandhiChecker
from app.karaka_syntax import (
    KarakaSyntaxEngine, SyntaxIssue, SamasaAnalysis, PRONOUN_MAP, _pronoun_lookup,
    AVYAYA_KRT, _strip_it_markers,
)
from app.verb_grammar import VerbForm, VerbGrammar


# Regex to isolate Sanskrit Devanagari word tokens, excluding dandas (।, ॥) and punctuation
WORD_PATTERN = re.compile(
    r"[\u0901-\u0939\u093d-\u094f\u0951-\u0954\u0958-\u0963\u0970-\u097f]+"
)

# Common Sanskrit grammatical error patterns and their Paninian corrections
COMMON_GRAMMAR_SUGGESTIONS: dict[str, tuple[str, str, str]] = {
    "gamati": (
        "gacCati",
        "इषुगमियमां छः (७.३.७७)",
        "धातु 'गम्' (gam) takes 'गच्छ' आदेश in सार्वधातुक लट् लकार प्रथम पुरुष: गच्छति (not गमति)",
    ),
    "gamatas": (
        "gacCatas",
        "इषुगमियमां छः (७.३.७७)",
        "धातु 'गम्' (gam) takes 'गच्छ' आदेश: गच्छतः",
    ),
    "gamanti": (
        "gacCanti",
        "इषुगमियमां छः (७.३.७७)",
        "धातु 'गम्' (gam) takes 'गच्छ' आदेश: गच्छन्ति",
    ),
    "gamasi": (
        "gacCasi",
        "इषुगमियमां छः (७.३.७७)",
        "धातु 'गम्' (gam) takes 'गच्छ' आदेश: गच्छसि",
    ),
    "gamaTa": (
        "gacCaTa",
        "इषुगमियमां छः (७.३.७७)",
        "धातु 'गम्' (gam) takes 'गच्छ' आदेश: गच्छथ",
    ),
    "gamAmi": (
        "gacCAmi",
        "इषुगमियमां छः (७.३.७७)",
        "धातु 'गम्' (gam) takes 'गच्छ' आदेश: गच्छामि",
    ),
    "sTAti": (
        "tizWati",
        "पाघ्राध्मास्था... (७.३.७८)",
        "धातु 'स्था' (sthā) takes 'तिष्ठ' आदेश in लट् लकार: तिष्ठति",
    ),
    "dfSyati": (
        "paSyati",
        "पाघ्राध्मास्था... (७.३.७८)",
        "धातु 'दृश्' (dṛś) takes 'पश्य' आदेश in लट् लकार परस्मैपद: पश्यति",
    ),
    "GrAti": (
        "jiGrati",
        "पाघ्राध्मास्था... (७.३.७८)",
        "धातु 'घ्रा' (ghrā) takes 'जिघ्र' आदेश: जिघ्रति",
    ),
    "pAti": (
        "pibati",
        "पाघ्राध्मास्था... (७.३.७८)",
        "धातु 'पा' (pā - to drink) takes 'पिब्' आदेश: पिबति",
    ),
}

# Phonetic/visual confusability classes used only to constrain which letter
# substitutions the general spelling-candidate generator below will try --
# these are standard Devanagari confusion groups (vowel length, dental vs.
# retroflex, sibilants, labial glide), not a table of specific answers. This
# keeps candidate generation from wandering into unrelated real words that
# happen to be one raw character away with no phonetic relationship at all.
SLP1_CONFUSABLE_GROUPS = [
    "aA", "iI", "uU", "fF", "xX", "eE", "oO",   # vowel length
    "tw", "TW", "dq", "DQ", "nR",                 # dental <-> retroflex pairs
    "kK", "gG", "cC", "jJ", "wW", "qQ", "tT", "dD", "pP", "bB",  # aspirated <-> unaspirated
    "sSz",                                         # sibilants
    "bv",                                          # labial/labio-dental glide
    "mMn",                                         # anusvara vs. a written nasal consonant
]


def _confusable_letters(ch: str) -> set[str]:
    out: set[str] = set()
    for group in SLP1_CONFUSABLE_GROUPS:
        if ch in group:
            out.update(group)
    out.discard(ch)
    return out

# How a pada's final letter may be written, and what it can stand for
# underlyingly. A word reaches the lexicon under whichever of these spellings
# the corpus happened to store, so every lookup path normalizes through the
# same table (see SanskritEngine._padanta_variants).
#
# The voiced-stop rows are जश्त्व (८.२.३९ झलां जशोऽन्ते): a pada-final
# voiceless stop is written voiced before a voiced sound, which is why
# उपरिष्टात् is also written उपरिष्टाद्. The dental pair (-द् for -त्) is by
# far the commonest, but the family is listed in full rather than singling
# that one out, since the rule is not specific to the dental series.
PADANTA_FINAL_VARIANTS: dict[str, tuple[str, ...]] = {
    "H": ("s", "r"),    # visarga for underlying -s / -r
    "o": ("as",),       # -o for underlying -as (६.१.११३ अतो रोरप्लुतादप्लुते)
    "M": ("m",),        # anusvara for a pada-final -m
    # यण् (६.१.७७ इको यणचि): a pada-final इ/उ/ऋ becomes य्/व्/र् before a
    # vowel, so इति is written इत्य् and एतासु is written एतास्व् whenever the
    # next word begins with a vowel. Editions vary on whether they then print
    # the two words joined or spaced, and when spaced the यण्-final fragment
    # arrives here as a token of its own.
    "y": ("i", "I"),
    "v": ("u", "U"),
    "r": ("s", "f", "F"),   # repha for underlying -s, and यण् for -ऋ
    "d": ("t",),        # जश्त्व: dental
    "b": ("p",),        # जश्त्व: labial
    "g": ("k",),        # जश्त्व: velar
    "q": ("w",),        # जश्त्व: retroflex
    "j": ("c",),        # जश्त्व: palatal
}

# The traditional उपसर्गs plus the अव्ययs that head an अव्ययीभाव. Used only
# to recognise a compound whose *whole* is absent from the Kosha but whose
# parts are not; never to segment or rewrite a token.
UPASARGA_PREFIXES = frozenset({
    "pra", "parA", "apa", "sam", "anu", "ava", "nis", "niH", "dus", "duH",
    "vi", "A", "ni", "aDi", "api", "ati", "su", "ud", "aBi", "prati", "pari",
    "upa", "yaTA", "sa",
})

# The अव्ययs that head an अव्ययीभाव often enough to be worth checking its
# ending (samāsa plan C4, docs/vidyut-phase-scope.md §10). Deliberately
# narrower than UPASARGA_PREFIXES: सु, सम्, वि, प्र and the like head far
# more प्रादि-तत्पुरुष and बहुव्रीहि compounds than अव्ययीभावs, and a declined
# ending is correct on those. Longest first, so यावत् is tried before या-.
AVYAYIBHAVA_HEADS = ("yAvat", "antar", "bahis", "prati", "yaTA", "upa", "anu", "aDi")

# महत् as the first member of a compound, as it is actually written: the final
# त् assimilates to what follows (महद्देवः, महन्नाम, महच्चरितम्, महज्जनः,
# महल्लोकः), so all of its पदान्त spellings are tried (samāsa plan C5a).
MAHAT_SPELLINGS = ("mahat", "mahad", "mahan", "mahac", "mahaj", "mahal")

# Last members of an "X and the rest" / "headed by X" compound. In these X is
# the thing listed, never a quality of the last member, so महत् in महदादि
# ("Mahat and the rest") cannot be समानाधिकरण with it and ६.३.४६ does not
# apply. Found on DCS text, where महदादि had drawn a महादि suggestion.
LISTING_FINAL_MEMBERS = frozenset({"Adi", "Adya", "praBfti", "pramuKa"})

# The अच् (vowels) in SLP1, simple and diphthong.
_VOWELS = frozenset("aAiIuUfFxXeEoO")

# The core सर्वनाम (pronominal) stems. A piece of a fused token whose Kosha
# reading has one of these stems is a pronoun in some case -- तस्य, येन,
# एतेषु -- which is the class, alongside the अव्ययs, that external sandhi
# routinely fuses to a neighbouring word in print.
PRONOMINAL_STEMS = frozenset({
    "tad", "yad", "etad", "idam", "adas", "kim", "asmad", "yuzmad",
})

# Common phonetic/orthographic typing substitutions
ORTHOGRAPHIC_SUBSTITUTIONS = [
    ("Dy", "dy", "'द्य' (द् + य) should be used instead of 'ध्य' (ध् + य)"),
    ("D", "dy", "'ध' may be a mistyped 'द्य' (द् + य) conjunct"),
    ("S", "z", "'ष' should be used instead of 'श'"),
    ("z", "S", "'श' should be used instead of 'ष'"),
    ("s", "S", "'श' should be used instead of 'स'"),
    ("s", "z", "'ष' should be used instead of 'स'"),
    ("n", "R", "'ण' should be used instead of 'न'"),
    ("R", "n", "'न' should be used instead of 'ण'"),
    ("b", "v", "'व' should be used instead of 'ब'"),
    ("v", "b", "'ब' should be used instead of 'व'"),
    ("ri", "f", "'ऋ' should be used instead of 'रि'"),
]

# Display names for a तिङन्त's lakara/prayoga. The analysis string used to
# state "लट्लकारः, कर्तरि प्रयोगः" as a literal, which was true only because
# VerbGrammar derived nothing else; it would have mislabelled every form as
# लट्-कर्तरि the moment it derived more.
LAKARA_DEVA: dict[str, str] = {
    "Lat": "लट्", "Lit": "लिट्", "Lut": "लुट्", "Lrt": "लृट्", "Let": "लेट्",
    "Lot": "लोट्", "Lan": "लङ्", "VidhiLin": "विधिलिङ्", "AshirLin": "आशीर्लिङ्",
    "Lun": "लुङ्", "Lrn": "लृङ्",
}
PRAYOGA_DEVA: dict[str, str] = {
    "Kartari": "कर्तरि", "Karmani": "कर्मणि", "Bhave": "भावे",
}


def _tinanta_analysis(root_deva: str, vf) -> str:
    """The तिङन्त analysis string, reading the form's own lakara/prayoga."""
    lakara = LAKARA_DEVA.get(vf.lakara.name, vf.lakara.name)
    prayoga = PRAYOGA_DEVA.get(vf.prayoga.name, vf.prayoga.name)
    return (
        f"तिङन्त (धातुः {root_deva}, पुरुषः {vf.purusha.name}, वचनम् {vf.vacana.name}, "
        f"{lakara}लकारः, {prayoga} प्रयोगः)"
    )


@dataclass
class TokenResult:
    text_deva: str          # the token in Devanagari, as written / segmented
    text_slp1: str          # the token in SLP1
    underlying_slp1: str    # normalized pada in SLP1 (e.g. rAmas for rAmaH)
    lemma: Optional[str]    # dictionary root/stem
    is_valid: bool          # True if recognized
    status: str = "valid"   # "valid" | "invalid" | "sandhi_error" | "samasa_error" | "karaka_error" | "agreement_error"
    severity: str = "error"  # "error" (confirmed problem) | "review" (offered, not asserted)
    analysis: Optional[str] = None
    suggestion: Optional[str] = None
    rule: Optional[str] = None
    sandhi_issue: Optional[str] = None
    karaka_issue: Optional[str] = None
    samasa_issue: Optional[str] = None
    # Structured grammatical readings, used for real agreement/kAraka analysis
    # instead of string-matching a description. Populated from vidyut.kosha
    # Subanta entries and from VerbGrammar's Paninian-derived tiNanta index.
    nominal_entries: list = field(default_factory=list)
    verb_readings: list = field(default_factory=list)
    # Lets the syntax layer ask the Kosha follow-up questions about this token
    # (e.g. how it would read with a dropped visarga restored) without the
    # syntax layer holding a Kosha handle of its own.
    kosha_lookup: object = None


@dataclass
class CheckResult:
    input_text: str
    tokens: list[TokenResult] = field(default_factory=list)
    syntax_issues: list[SyntaxIssue] = field(default_factory=list)
    compounds: list[SamasaAnalysis] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        """Confirmed problems only. Never counts a 'review'-severity finding --
        an unrecognised word or an unapplied-but-optional sandhi is offered for
        human judgement, not asserted as a defect."""
        return sum(1 for t in self.tokens if t.status != "valid" and t.severity == "error")

    @property
    def review_count(self) -> int:
        return sum(1 for t in self.tokens if t.status != "valid" and t.severity == "review")

    @property
    def sandhi_error_count(self) -> int:
        return sum(1 for t in self.tokens if t.status == "sandhi_error" and t.severity == "error")

    @property
    def syntax_error_count(self) -> int:
        return sum(
            1 for t in self.tokens
            if t.status in ["karaka_error", "agreement_error", "upapada_error"]
            and t.severity == "error"
        )


class SanskritEngine:
    """Loads vidyut data, supplemental lexicon, sandhi rules, and Karaka/Syntax engine."""

    def __init__(self, data_dir: str | Path):
        data_dir = Path(data_dir)
        self._chedaka = Chedaka(str(data_dir))
        self._kosha = Kosha(str(data_dir / "kosha"))
        self._lexicon = SupplementalLexicon()
        self._sandhi_checker = SandhiChecker(data_dir / "sandhi" / "rules.csv")
        self._verb_grammar = VerbGrammar(data_dir / "prakriya", kosha=self._kosha)
        self._karaka_engine = KarakaSyntaxEngine(self._verb_grammar)

    def _describe(self, entry) -> str:
        """User-friendly grammatical description of a kosha entry."""
        return str(entry)

    @staticmethod
    def _pick_best_entry(entries: list):
        """The most likely reading among several homographic Kosha entries,
        for display purposes (lemma/analysis shown to the user).

        A surface form can be genuinely ambiguous (राम: also matches a rare
        कृदन्त bahuvacana reading of the unrelated root रम्, alongside the
        ordinary proper-noun reading), and vidyut does not rank entries by
        frequency, so entries[0] can be a rare homograph rather than the
        obvious intended word. An ordinary/basic nominal reading in the
        singular is preferred over a secondary (कृदन्त-derived) or
        plural/dual reading when both are available.
        """
        def rank(e):
            kind = type(getattr(e, "pratipadika_entry", None)).__name__
            is_basic = 0 if kind.endswith("Basic") else 1
            vacana = getattr(e, "vacana", None)
            is_eka = 0 if (vacana is None or getattr(vacana, "name", None) == "Eka") else 1
            return (is_basic, is_eka)
        return sorted(entries, key=rank)[0]

    def _padanta_variants(self, slp1_word: str) -> list[str]:
        """The underlying pada forms a surface word-final letter may stand for.

        A pada's final letter is not written the same way in every context, so
        the same word reaches the lexicon under more than one spelling. Rather
        than a per-ending ladder of near-identical lookups, the pairs live in
        `PADANTA_FINAL_VARIANTS` and every lookup path walks the same list --
        `_raw_check` and `_raw_kosha_entries` previously carried two
        hand-maintained copies of this that had already drifted apart (the
        supplemental lexicon was consulted for some endings but not others).
        """
        out: list[str] = []
        for final, underlying in PADANTA_FINAL_VARIANTS.items():
            if slp1_word.endswith(final):
                stem = slp1_word[: -len(final)]
                out.extend(stem + u for u in underlying)
        return out

    def _kosha_hit(self, cand: str):
        """(lemma_deva, analysis) for a Kosha form, or None."""
        entries = list(self._kosha.get(cand))
        if not entries:
            return None
        first = self._pick_best_entry(entries)
        lemma = getattr(first, "lemma", None)
        lemma_deva = transliterate(lemma, Scheme.Slp1, Scheme.Devanagari) if lemma else None
        analysis = self._describe(first)
        if len(entries) > 1:
            analysis += f"  (+{len(entries) - 1} other possible analyses)"
        return lemma_deva, analysis

    def _raw_check(self, slp1_word: str) -> tuple[bool, Optional[str], Optional[str], str]:
        """Internal helper to test word existence without triggering suggestions loop."""
        for cand in [slp1_word, *self._padanta_variants(slp1_word)]:
            lex_entry = self._lexicon.lookup(cand)
            if lex_entry:
                lemma_deva = transliterate(lex_entry.lemma, Scheme.Slp1, Scheme.Devanagari)
                return True, lemma_deva, lex_entry.analysis, lex_entry.text_slp1
            hit = self._kosha_hit(cand)
            if hit:
                return True, hit[0], hit[1], cand
        return False, None, None, slp1_word

    def _raw_kosha_entries(self, slp1_word: str) -> list:
        """All raw vidyut.kosha entries for a surface form, trying the same
        padanta normalizations as `_raw_check`, but returning every candidate
        reading rather than an arbitrary first one -- callers that need real
        grammatical categories (vibhakti, vacana, ...) must inspect all
        candidates themselves rather than trust entries[0], which is not
        ranked by frequency and can be a rare homograph (e.g. रामः also
        matches a कृदन्त bahuvacana reading of the unrelated root रम्)."""
        for cand in [slp1_word, *self._padanta_variants(slp1_word)]:
            entries = list(self._kosha.get(cand))
            if entries:
                return entries
        return []

    def _is_upasarga_compound(self, slp1_word: str) -> bool:
        """True for a compound headed by an उपसर्ग/अव्यय whose remainder is an
        independently recognised word ending in -अम्.

        अव्ययीभाव adverbials -- प्रतिदिनम्, प्रतिमासम्, यथाक्रमम् -- are
        ordinary everyday vocabulary, and the Kosha carries most of them
        (प्रत्यहम्, प्रतिवर्षम्, प्रतिक्षणम्, अनुदिनम्, उपकूलम्, प्रत्येकम्
        … 11 of 16 sampled) but not all. The holes are individual lexical
        gaps in a finite list, not the long-compound segmentation ceiling, so
        they are worth closing -- and vidyut 0.4.0 has no समास support at all,
        so they cannot be closed by derivation.

        The -अम् requirement is नाव्ययीभावादतोऽम्त्वपञ्चम्याः (२.४.८३), and it
        is what makes this safe rather than general prefix-stripping: it
        excludes उपसर्ग-prefixed *verbs* (परिमुच्यते, परिक्षरति) which are a
        different question, and it excludes परिक्षा -- a genuine typo for
        परीक्षा that a bare prefix-strip would have validated as परि + क्षा.
        Verified against every typo in the gold set: none is validated here.

        This only ever moves a token from review to valid. It cannot cause a
        confirmed-tier flag, so its failure mode is a missed error, never a
        wrong accusation.
        """
        for prefix in sorted(UPASARGA_PREFIXES, key=len, reverse=True):
            if not slp1_word.startswith(prefix) or len(slp1_word) <= len(prefix) + 3:
                continue
            rest = slp1_word[len(prefix):]
            if rest.endswith(("am", "aM")) and self._raw_check(rest)[0]:
                return True
        return False

    @staticmethod
    def _avyayibhava_form(stem: str) -> Optional[tuple[str, str]]:
        """(the अव्ययीभाव spelling of a final member, the sūtra that makes it).

        The compound is neuter (अव्ययीभावश्च १.१.४१ makes it an अव्यय), so a
        long final vowel is shortened (ह्रस्वो नपुंसके प्रातिपदिकस्य १.२.४७);
        an अ-final member then takes -अम् (नाव्ययीभावादतोऽम्त्वपञ्चम्याः
        २.४.८३), and any other vowel-final member takes no ending at all
        (अव्ययादाप्सुपः २.४.८२). Consonant-final members are left alone: their
        treatment (अनश्च ५.४.१०८ and its neighbours) is not modelled here.
        """
        final = stem[-1:]
        if final == "a":
            return stem + "m", "नाव्ययीभावादतोऽम्त्वपञ्चम्याः (२.४.८३)"
        if final == "A":
            return stem[:-1] + "am", "ह्रस्वो नपुंसके प्रातिपदिकस्य (१.२.४७)"
        if final in ("I", "U"):
            return stem[:-1] + ("i" if final == "I" else "u"), "ह्रस्वो नपुंसके प्रातिपदिकस्य (१.२.४७)"
        if final in ("i", "u"):
            return stem, "अव्ययादाप्सुपः (२.४.८२)"
        return None

    def _avyayibhava_candidates(self, slp1_word: str) -> Optional[tuple[str, str, str]]:
        """(head, expected spelling, sūtra) if the word is an अव्ययीभाव head
        followed by a form of exactly one kind of final member; else None.

        Only ordinary (Basic) प्रातिपदिकs are read as the final member: a
        कृदन्त entry's "lemma" is its root, not its stem, so it cannot give the
        spelling. If the member's readings disagree on what the compound
        should look like, nothing is proposed -- the check declines rather
        than choosing.
        """
        for head in AVYAYIBHAVA_HEADS:
            if not slp1_word.startswith(head) or len(slp1_word) - len(head) < 3:
                continue
            rest = slp1_word[len(head):]
            expected = set()
            for entry in self._raw_kosha_entries(rest):
                pe = getattr(entry, "pratipadika_entry", None)
                if pe is None or not type(pe).__name__.endswith("Basic"):
                    continue
                form = self._avyayibhava_form(pe.lemma)
                if form:
                    expected.add((head + form[0], form[1]))
            if not expected:
                continue
            if len({f for f, _ in expected}) != 1:
                return None
            # Readings can agree on the spelling but reach it by different
            # rules -- गङ्गाम् carries both गङ्गा and गङ्ग -- so cite the one that
            # actually changes what is written, the shortening, when present.
            spelling = next(iter(expected))[0]
            sutras = {s for _, s in expected}
            shortening = next((s for s in sutras if "१.२.४७" in s), None)
            return head, spelling, shortening or sorted(sutras)[0]
        return None

    def _is_avyayibhava_luk_form(self, slp1_word: str) -> bool:
        """True for an अव्ययीभाव whose final member takes no ending at all --
        यथाशक्ति, उपनदि (अव्ययादाप्सुपः २.४.८२). The -अम् kind is already
        recognised by `_is_upasarga_compound`; this is its counterpart for
        इ/उ-final members, which had no recognition path and so drew a ⚪ on
        perfectly correct words.

        Limited to the यथा- head. A bare इ/उ-final word is also exactly what a
        dropped visarga looks like -- अनुभूति for अनुभूतिः -- and under उप/अनु/
        प्रति an इ-stem is as often a प्रादि noun as an अव्ययीभाव, so accepting it
        there would silence a missing-visarga typo, and would do it ahead of
        the spelling corrector that asserts it. यथा- compounds on an इ/उ member
        (यथाशक्ति, यथामति, यथारुचि) are अव्ययीभाव in practice.

        Like its counterpart this only ever moves a token from review to
        valid, so its failure mode is a missed error, never an accusation.
        """
        found = self._avyayibhava_candidates(slp1_word)
        return (found is not None and found[0] == "yaTA" and found[1] == slp1_word
                and slp1_word[-1:] in ("i", "u"))

    def _avyayibhava_ending_issue(self, slp1_word: str) -> Optional[tuple[str, str, str]]:
        """(expected spelling, sūtra, explanation) for an *unrecognised* word
        that reads as an अव्ययीभाव written with a case ending -- उपगङ्गाम् for
        उपगङ्गम्, प्रतिदिनेषु for प्रतिदिनम्, यथाशक्तिः for यथाशक्ति.

        Callers must only ask this of a word the lexicon does not carry. That
        gate is what makes it safe: a declined ending is correct on a
        प्रादि-तत्पुरुष or बहुव्रीहि with the same head (उपवनानि, उपकरणानि,
        प्रतिज्ञाम्), and every one of those sampled is in the Kosha. The
        optional -आत्, -एन and -ए forms of an अ-final member (तृतीयासप्तम्योर्बहुलम्
        २.४.८४, and the पञ्चमी exception in २.४.८३) are accepted, not flagged.

        Offered at review tier only: the head alone does not prove the word is
        an अव्ययीभाव rather than an unlisted प्रादि compound.
        """
        found = self._avyayibhava_candidates(slp1_word)
        if found is None:
            return None
        head, spelling, sutra = found
        if spelling == slp1_word:
            return None
        if spelling.endswith("am"):
            base = spelling[:-2]
            if slp1_word in (base + "At", base + "Ad", base + "ena", base + "e"):
                return None
        spelling_deva = transliterate(spelling, Scheme.Slp1, Scheme.Devanagari)
        head_deva = transliterate(head, Scheme.Slp1, Scheme.Devanagari)
        explanation = (
            f"Read as an अव्ययीभाव compound headed by '{head_deva}', this should be "
            f"written '{spelling_deva}': the compound is an indeclinable (अव्ययीभावश्च "
            f"१.१.४१) and does not take this case ending. If it is instead a different "
            f"kind of compound with the same prefix, the word may be correct as written."
        )
        return spelling_deva, sutra, explanation

    def _mahat_compound_issue(self, slp1_word: str) -> Optional[tuple[str, str, str]]:
        """(expected spelling, sūtra, explanation) for an *unrecognised* word
        written महत्- + a known word -- महत्पुरुषः for महापुरुषः, महदीश्वरः for
        महेश्वरः (आन्महतः समानाधिकरणजातीययोः ६.३.४६).

        The sūtra covers only a कर्मधारय or बहुव्रीहि, where महत् describes the
        other member ("a great man"). In a षष्ठी-तत्पुरुष ("service of the
        great") महत्- is correct as written, and form alone cannot tell the two
        apart -- so, like the अव्ययीभाव check, this is only asked of a word the
        lexicon does not carry, and is offered at review tier. Every correct
        महत्- word sampled (महत्सेवा, महत्त्वम्, महत्तरः, महत्तमः, महद्भ्यः) is in
        the Kosha.
        """
        for spelling in MAHAT_SPELLINGS:
            if not slp1_word.startswith(spelling) or len(slp1_word) - len(spelling) < 3:
                continue
            rest = slp1_word[len(spelling):]
            lemmas = {e.pratipadika_entry.lemma for e in self._raw_kosha_entries(rest)
                      if type(getattr(e, "pratipadika_entry", None)).__name__.endswith("Basic")}
            if not lemmas:
                continue
            if lemmas & LISTING_FINAL_MEMBERS:
                return None   # see `_is_mahat_listing_compound`
            joined = None
            if rest[:1] in ("a", "A", "i", "I", "u", "U", "f", "F", "e", "E", "o", "O"):
                sandhi = self._sandhi_checker.apply_sandhi("mahA", rest)
                joined = sandhi[0] if sandhi else None
            expected = joined or ("mahA" + rest)
            expected_deva = transliterate(expected, Scheme.Slp1, Scheme.Devanagari)
            explanation = (
                f"If महत् here describes the other member (\"a great …\"), it becomes महा- "
                f"in the compound: '{expected_deva}'. If the compound instead means "
                f"\"… of the great\", महत्- is correct as written."
            )
            return expected_deva, "आन्महतः समानाधिकरणजातीययोः (६.३.४६)", explanation
        return None

    def _is_mahat_listing_compound(self, slp1_word: str) -> bool:
        """True for महत्- + आदि/आद्य/प्रभृति/प्रमुख (महदादि, "Mahat and the rest").

        Correct as written, and not in the Kosha. It is neither recognised nor
        flagged: its absence from the lexicon is explained, so it must not be
        handed to the edit-distance corrector, which asserted महदादि -> महदाद्
        at 🔴. It stays an ordinary ⚪ unrecognised word.
        """
        for spelling in MAHAT_SPELLINGS:
            if slp1_word.startswith(spelling) and len(slp1_word) - len(spelling) >= 3:
                rest = slp1_word[len(spelling):]
                lemmas = {e.pratipadika_entry.lemma for e in self._raw_kosha_entries(rest)
                          if type(getattr(e, "pratipadika_entry", None)).__name__.endswith("Basic")}
                if lemmas & LISTING_FINAL_MEMBERS:
                    return True
        return False

    def _repha_base(self, base_slp1: str) -> str:
        """Rewrite a पदान्त visarga/-स् to -र् where the word really ends in -र्.

        A final visarga can stand for either (`PADANTA_FINAL_VARIANTS`), and
        the junction code assumed -स् throughout, so पुनः before a voiced sound
        was offered as पुनो by हशि च (६.१.११४). पुनर्, प्रातर् and अन्तर् end in
        -र्, whose junction is different: the र् simply stays (पुनर्गुरोः,
        पुनरपि), or drops with the preceding vowel lengthened before another
        र् (प्राता रामः, रो रि ८.३.१४ / ढ्रलोपे पूर्वस्य दीर्घोऽणः ६.३.१११).
        vidyut's own rules.csv already produces all of that once it is handed
        the -र् form.

        The -र् spelling is trusted only when the Kosha reads it as an
        *अव्यय*. That is what separates these indeclinables, whose pada really
        ends in र्, from an ordinary -अस् nominal: पुनस्/प्रातस्/अन्तस् have no
        अव्यय reading, and neither does गुरोर्, whose -र् arises by sandhi
        (सस्जुषो रुः ८.२.६६) rather than being lexical. That other class is a
        separate gap and is deliberately not touched here.
        """
        if not base_slp1.endswith(("H", "s")):
            return base_slp1
        r_form = base_slp1[:-1] + "r"
        if any(getattr(getattr(e, "pratipadika_entry", None), "is_avyaya", False)
               for e in self._kosha.get(r_form)):
            return r_form
        return base_slp1

    def _is_recognized(self, slp1_word: str) -> bool:
        is_valid, *_ = self._raw_check(slp1_word)
        return is_valid or bool(self._verb_grammar.lookup(slp1_word))

    def _edit_distance_1_candidates(self, slp1_word: str) -> set[str]:
        """Every string reachable from `slp1_word` by one deletion, one
        phonetically-plausible substitution, a constrained insertion, or an
        adjacent-letter transposition.

        This is a general, grammar-agnostic spelling-candidate generator (the
        standard single-edit method used by ordinary spellcheckers), not a
        table of known confusions: it covers a missing visarga (insertion),
        a doubled consonant from OCR (deletion), and a misordered conjunct
        (transposition) with the same mechanism, and every candidate is
        validated against the real lexicon/verb-grammar before being trusted.

        Substitutions and insertions are restricted to phonetically/visually
        confusable letters (see SLP1_CONFUSABLE_GROUPS) plus the two most
        common omissions, visarga and anusvara. An unrestricted full-alphabet
        search finds far too many *unrelated* real words one raw character
        away (Sanskrit's morphology is productive enough that almost any
        short string is one substitution from some rare inflected form),
        which makes a confident single-candidate correction rare even for
        genuine typos; restricting to actual confusion classes keeps the
        search targeted at the errors people and OCR engines actually make.
        """
        n = len(slp1_word)
        candidates: set[str] = set()
        for i in range(n):
            # Never delete a word's *first* letter to reach another word.
            #
            # Word-initial material in Sanskrit is morphologically load-bearing
            # -- a नञ् negation (असामान्यशब्दः is not a typo of सामान्यशब्दः),
            # an उपसर्ग, or simply the stem itself -- so stripping it does not
            # repair a typo, it manufactures a different word. This is the
            # एकस्मिन् → कस्मिन् failure: एक is a perfectly good प्रातिपदिक and
            # एकस्मिन् its सर्वनाम locative, absent from the Kosha only because
            # of the upstream सर्वादि gap (see docs/vidyut-issue-eka-sarvadi.md);
            # deleting the initial ए reaches the unrelated कस्मिन् and the word
            # was then "corrected" into it.
            #
            # This costs nothing in recall: every genuine typo the gold set
            # catches has its edit at position >= 1 (verified across all 12 --
            # substitutions, transpositions and one internal deletion).
            if i == 0 and n > 1:
                continue
            candidates.add(slp1_word[:i] + slp1_word[i + 1:])
        for i in range(n - 1):
            if slp1_word[i] != slp1_word[i + 1]:
                candidates.add(slp1_word[:i] + slp1_word[i + 1] + slp1_word[i] + slp1_word[i + 2:])
        for i in range(n):
            for ch in _confusable_letters(slp1_word[i]):
                candidates.add(slp1_word[:i] + ch + slp1_word[i + 1:])
        for i in range(n + 1):
            candidates.add(slp1_word[:i] + "H" + slp1_word[i:])
            candidates.add(slp1_word[:i] + "M" + slp1_word[i:])
            # Reduplication/haplography: a doubled letter or syllable lost
            # (गच्छति -> गछति) or gained (अध्ययनम् -> अध्यनम्, dropping the
            # repeated य) is one of the most common Sanskrit typing/OCR slips.
            if i > 0:
                candidates.add(slp1_word[:i] + slp1_word[i - 1] + slp1_word[i:])
            if i > 1:
                candidates.add(slp1_word[:i] + slp1_word[i - 2:i] + slp1_word[i:])
        candidates.discard(slp1_word)
        return candidates

    def _is_productively_composite(self, slp1_word: str) -> bool:
        """True when this token looks like a productively-formed multi-word
        unit -- two or more padas fused by external sandhi -- rather than a
        single word that ought to be in the lexicon on its own.

        This is the evidence test that decides whether the token's *absence*
        from the lexicon means anything. Sandhi-fusion and compounding are
        open-ended: तथापि (तथा + अपि) and यश्च (यः + च) are perfectly correct
        Sanskrit that no finite dictionary of whole words can list, so
        "not found" tells us nothing about them. A simple word's absence, by
        contrast, is genuinely surprising and does carry information.

        Two conditions must both hold, and each is doing real work:

        1. Chedaka segments the token into 2+ pieces that it *all* recognises.
           Chedaka's own analysis, not a string search: splitting against a
           list of bare stems was measured and is vacuous -- with ~169k stems
           in the Kosha it "decomposes" गुरुः as guru+H and पठति as paWa+ti,
           which would veto everything.

        2. The surface is *not* the plain concatenation of those pieces --
           i.e. sandhi visibly applied at the junction (तथा + अपि -> तथापि
           changes the boundary; the pieces do not simply abut). Without this,
           any string that happens to cut into two dictionary words qualifies,
           and Chedaka supplies such cuts freely: विधालयः cuts as विधा+लयः and
           रामेन as रा+मेन, both plain concatenations of real words and both
           genuine typos we must keep catching.

        Deliberately *not* done here: nothing in the token stream is rewritten
        and the pieces are not substituted for the token downstream. Chedaka
        produces recognised-but-implausible splits freely (अहेतुमन् ->
        अह+इत्+उम्+अन्), so a split is treated only as evidence about whether
        absence is informative, never as an analysis to act on.
        """
        pieces = self._chedaka.run(slp1_word)
        if len(pieces) < 2:
            return False
        if any(p.data is None for p in pieces):
            return False
        # At least one piece must be a particle, indeclinable or pronoun.
        # This is what separates a fused pada pair from a compound. External
        # sandhi is printed as one graphic unit mainly around clitics and
        # pronouns -- च, तु, हि, अपि, इति, एव, न, तद्/इदम् -- as in तथापि,
        # यश्च, मध्यतस्तु, विशेषस्तस्य. Two *content* words written together
        # are a समास, which is a single word in its own right, so its absence
        # from the lexicon is informative and must stay checkable: विधालयः
        # segments just as neatly into विध + आलयः, and आशिर्वादः into
        # आशिस् + वादः, but both are misspelled compounds, not fusions.
        # This also drops the junk segmentations Chedaka offers freely, whose
        # pieces are neither content words nor real particles (अहेतुमन् ->
        # अह + इत् + उम् + अन्, शनैर् -> शन् + अ + अ + ईर्).
        if not any(self._is_function_word(p.text) for p in pieces):
            return False
        if "".join(p.text for p in pieces) != slp1_word:
            return True
        # The pieces abut, but the junction can still carry sandhi that this
        # comparison cannot see: Chedaka reports a pada in its underlying
        # -s/-r form, which at a real pada end would have surfaced as visarga
        # (विशेषः + तस्य -> विशेषस्तस्य keeps the स्, and मध्यतः + तु ->
        # मध्यतस्तु likewise). A non-final piece still ending in -s/-r is
        # therefore evidence that sandhi joined it to what follows, since
        # standing alone it would have been written -ः.
        return any(p.text.endswith(("s", "r")) for p in pieces[:-1])

    def _is_function_word(self, slp1_word: str) -> bool:
        """True if this surface form has an indeclinable or pronoun reading.

        The अव्यय inventory is vidyut's own: Kosha entries carry an
        `is_avyaya` flag on the prātipadika, which cleanly separates the
        particles that get written joined (च, तु, हि, खलु, अपि, इति, एव, न,
        अत्र, वै, स्म, अथ, इव, तथा, मध्यतः) from content words (विध, आलयः,
        आशिस्, वादः). Chedaka's own copy of that flag is not usable here --
        it reports `ca` and `atra` as non-avyaya -- so the Kosha is consulted
        directly. Pronouns come from PRONOUN_MAP, which already settles a
        pronoun's identity elsewhere in this engine.
        """
        if _pronoun_lookup(PRONOUN_MAP, slp1_word) is not None:
            return True
        for entry in self._raw_kosha_entries(slp1_word):
            pratipadika_entry = getattr(entry, "pratipadika_entry", None)
            pratipadika = getattr(pratipadika_entry, "pratipadika", None)
            if getattr(pratipadika, "is_avyaya", False):
                return True
            # अव्ययकृत्: क्त्वा / ल्यप् / तुमुन् form indeclinables
            # (क्त्वातोसुन्कसुनः १.१.४०, कृन्मेजन्तः १.१.३९). उक्त्वा and
            # गत्वा are as much particles-for-this-purpose as च or इति, and
            # इत्युक्त्वा (इति + उक्त्वा) is a fused pair that must not be
            # "corrected" to इत्युक्ता. The same test is applied to the
            # syntax layer's tokens by karaka_syntax._is_avyaya_token.
            krt = getattr(pratipadika_entry, "krt", None)
            if krt is not None and _strip_it_markers(str(krt)) in AVYAYA_KRT:
                return True
            # PRONOUN_MAP only lists the handful of surface forms this engine
            # needs elsewhere for पुरुष/वचन, so an oblique pronoun (तस्य, येन,
            # ...) is not in it. The stem the Kosha assigns settles the
            # question for the whole declension at once.
            if getattr(pratipadika, "text", None) in PRONOMINAL_STEMS:
                return True
        return False

    @staticmethod
    def _is_nasal_orthographic_variant(a: str, b: str) -> bool:
        """True when two spellings differ only by a licensed anusvāra /
        homorganic-nasal alternation, i.e. they are the same word written two
        equally correct ways.

        अनुस्वारस्य ययि परसवर्णः (८.४.५८) substitutes the homorganic nasal for
        anusvāra, so शंकरे and शङ्करे are both correct and choosing between
        them is house style, not grammar. Asserting one over the other as an
        error is exactly the kind of overclaiming that costs an author's
        trust, so no such "correction" is offered.

        The sūtra's ययि condition is enforced, not waved at, and it is what
        keeps this from swallowing real errors: यय् excludes the sibilants and
        ह, so before a sibilant the anusvāra has no parasavarṇa substitute and
        is the only correct spelling -- which is why संस्कृतम् is right and
        सन्स्कृतम् is a genuine error rather than a variant. The substitute
        must also be homorganic with what follows: न् before क् is not a
        licensed variant of anything.
        """
        # स्थान (place of articulation) -> the nasal of that class
        HOMORGANIC_NASAL = {
            **{c: "N" for c in "kKgGN"},   # कवर्ग
            **{c: "Y" for c in "cCjJY"},   # चवर्ग
            **{c: "R" for c in "wWqQR"},   # टवर्ग
            **{c: "n" for c in "tTdDn"},   # तवर्ग
            **{c: "m" for c in "pPbBm"},   # पवर्ग
        }
        if len(a) != len(b):
            return False
        diffs = [i for i, (x, y) in enumerate(zip(a, b)) if x != y]
        if not diffs:
            return False
        for i in diffs:
            pair = {a[i], b[i]}
            if "M" not in pair:
                return False
            following = a[i + 1] if i + 1 < len(a) else None
            if following is None or following != b[i + 1]:
                return False
            # यय्: every consonant except श ष स ह. A vowel or a sibilant after
            # the nasal leaves anusvāra with no licensed substitute.
            if HOMORGANIC_NASAL.get(following) is None and following not in "yvrl":
                return False
            expected = HOMORGANIC_NASAL.get(following, following)
            if (pair - {"M"}) != {expected}:
                return False
        return True

    def _find_spelling_correction(self, slp1_word: str) -> Optional[str]:
        """A single lexicon-verified one-edit fix, or None if zero or several
        candidates validate -- an ambiguous or unmatched word is left for
        human review rather than guessed at. Precision matters more than
        recall here: asserting a confident but wrong "fix" on a word that
        was already fine is worse than leaving a genuine typo at review tier.

        An unrecognised word is not evidence of an error. "I do not know this
        word" plus "one edit reaches a word I do know" is only worth asserting
        when the word's absence from the lexicon is itself informative --
        see `_is_productively_composite`, which is what decides that. A fused
        pada-pair is returned unchanged so it stays at review tier, where an
        unrecognised word belongs, instead of being confidently rewritten into
        some unrelated word that happens to sit one edit away.
        """
        if self._is_productively_composite(slp1_word):
            return None

        valid = [c for c in self._edit_distance_1_candidates(slp1_word) if self._is_recognized(c)]
        if len(valid) != 1:
            return None

        suggested = valid[0]
        if self._is_nasal_orthographic_variant(slp1_word, suggested):
            return None
        return suggested

    def check_word(
        self, slp1_word: str
    ) -> tuple[bool, Optional[str], Optional[str], str, Optional[str], Optional[str]]:
        """Look up an SLP1-encoded word in lexicon and check for corrections.

        Returns (is_valid, lemma, analysis, underlying_slp1, suggestion_deva, rule_citation).
        """
        is_valid, lemma_deva, analysis, underlying = self._raw_check(slp1_word)

        # A finite verb outranks a nominal homograph for display purposes.
        #
        # भवति is the लट् third-person of भू, and that is what VerbGrammar
        # derives; but the Kosha also carries भवत् (the honorific, and the
        # शतृ participle) whose Saptamī singular is spelled the same, and
        # _pick_best_entry's preference for an ordinary Basic stem handed the
        # display to *that* -- so the tool reported "Stem/Root: भवत्" for a
        # form of भू. The derivation was never wrong and the syntax layer
        # always read the token as a verb; only the label was wrong.
        #
        # Restricted to a Prathama-puruṣa reading so a noun that merely
        # collides with some rare paradigm cell keeps its nominal identity --
        # भावः matches an उत्तम dual of भा and must stay the noun भाव.
        verb_forms = self._verb_grammar.lookup(slp1_word)
        if verb_forms and any(vf.purusha.name == "Prathama" for vf in verb_forms):
            vf = next(v for v in verb_forms if v.purusha.name == "Prathama")
            root_deva = transliterate(
                self._verb_grammar.clean_root(vf.aupadeshika), Scheme.Slp1, Scheme.Devanagari)
            verb_analysis = _tinanta_analysis(root_deva, vf)
            if is_valid:
                verb_analysis += "  (also readable as a nominal homograph)"
            return True, root_deva, verb_analysis, underlying if is_valid else slp1_word, None, None

        if is_valid:
            return True, lemma_deva, analysis, underlying, None, None

        # Genuine Paninian tiNanta check: is this an exact form the Dhatupatha's
        # laT-kartari derivation actually produces for some root? (a real
        # vidyut.prakriya derivation, not a lookup table of known-good forms).
        # This recognises every root in the Dhatupatha, not only the handful
        # covered by the base kosha's incidental participle homographs.
        verb_forms = self._verb_grammar.lookup(slp1_word)
        if verb_forms:
            vf = verb_forms[0]
            root_deva = transliterate(
                self._verb_grammar.clean_root(vf.aupadeshika), Scheme.Slp1, Scheme.Devanagari)
            analysis = _tinanta_analysis(root_deva, vf)
            return True, root_deva, analysis, slp1_word, None, None

        # An अव्ययीभाव / उपसर्ग compound whose parts are known but whose whole
        # the Kosha does not list (प्रतिदिनम्). Recognised, not corrected.
        if self._is_upasarga_compound(slp1_word) or self._is_avyayibhava_luk_form(slp1_word):
            return True, None, "अव्ययीभाव / उपसर्ग-समास (recognised from its members)", slp1_word, None, None

        # Check for grammatical substitution suggestions (e.g. gamati -> gacCati)
        if slp1_word in COMMON_GRAMMAR_SUGGESTIONS:
            sug_slp1, sutra, exp = COMMON_GRAMMAR_SUGGESTIONS[slp1_word]
            sug_deva = transliterate(sug_slp1, Scheme.Slp1, Scheme.Devanagari)
            return False, None, exp, slp1_word, sug_deva, sutra

        # Everything below asserts a defect on the strength of the word not
        # being in the lexicon, so it is gated on that absence being
        # informative in the first place -- see `_is_productively_composite`.
        # Without this the fixed confusion table below would still "correct"
        # शनैर् to शणैर् on a token that is simply a sandhi-fused pada pair.
        if self._is_productively_composite(slp1_word):
            return False, None, None, slp1_word, None, None

        # Same reasoning for a word that reads as a samāsa written against a
        # samāsa rule (अनुगङ्गाम्, प्रतिमासाः, महत्पुरुषः): its absence from the
        # lexicon is already explained, and the explanation comes with the
        # rule's own spelling. Left to the correctors below it was being
        # "fixed" by edit distance instead -- प्रतिमासाः became the unrelated
        # प्रतिमांसाः and was asserted 🔴, and अनुगङ्गाम् reached the right
        # spelling under a spelling-error label. Returning no suggestion here
        # hands the word to `check_text`, which raises the ⚪ samāsa note.
        if (self._avyayibhava_ending_issue(slp1_word) or self._mahat_compound_issue(slp1_word)
                or self._is_mahat_listing_compound(slp1_word)):
            return False, None, None, slp1_word, None, None

        # Check for orthographic/spelling typing substitutions (e.g. viDyArTI -> vidyArTI)
        for old, new, reason in ORTHOGRAPHIC_SUBSTITUTIONS:
            if old in slp1_word:
                cand = slp1_word.replace(old, new)
                c_valid, c_lemma, c_ana, _ = self._raw_check(cand)
                if c_valid:
                    cand_deva = transliterate(cand, Scheme.Slp1, Scheme.Devanagari)
                    return (
                        False,
                        None,
                        f"Spelling error: {reason}",
                        slp1_word,
                        cand_deva,
                        "वर्ण-शुद्धिः (Spelling Correction)",
                    )

        # General fallback: any recognised word reachable by a single letter
        # edit (insertion/deletion/substitution/transposition). Covers cases
        # the fixed confusion table above does not name outright -- a missing
        # visarga, a doubled consonant, a misordered conjunct -- without
        # hardcoding the specific pairs, since every candidate is checked
        # against the real lexicon/verb-grammar and only a single unambiguous
        # match is trusted.
        general_fix = self._find_spelling_correction(slp1_word)
        if general_fix:
            fix_deva = transliterate(general_fix, Scheme.Slp1, Scheme.Devanagari)
            return (
                False,
                None,
                "Spelling: exactly one recognised form is a single letter away",
                slp1_word,
                fix_deva,
                "वर्ण-शुद्धिः (Spelling Correction)",
            )

        return False, None, None, slp1_word, None, None

    def check_sandhi_boundary(
        self,
        surface_w1_slp1: str,
        surface_w2_slp1: str,
        underlying_w1_slp1: str,
        underlying_w2_slp1: str,
    ):
        """Validates the sandhi junction between two adjacent tokens."""
        return self._sandhi_checker.check_junction(
            surface_w1_slp1,
            surface_w2_slp1,
            underlying_w1_slp1,
            underlying_w2_slp1,
        )

    def check_text(self, devanagari_text: str) -> CheckResult:
        """Performs token extraction, word validity, spelling checks, sandhi verification, and Karaka/Syntax checks."""
        clean_text = devanagari_text.strip()
        result = CheckResult(input_text=devanagari_text)

        if not clean_text:
            return result

        # Extract words using WORD_PATTERN (excludes dandas ।, ॥ and all punctuation)
        words_deva = WORD_PATTERN.findall(clean_text)

        if not words_deva:
            return result

        # 1. Analyze each surface token
        for w_deva in words_deva:
            w_slp1 = transliterate(w_deva, Scheme.Devanagari, Scheme.Slp1)
            is_valid, lemma, analysis, underlying_slp1, suggestion, rule = self.check_word(w_slp1)

            status = "valid" if is_valid else "invalid"
            # An unrecognised word with no validated correction is sent for
            # human review, not asserted as a defect -- it is very often a
            # proper noun, place name or technical term. Only a word for which
            # a specific, lexicon-verified fix was found is a confirmed error.
            severity = "error" if (is_valid or suggestion is not None) else "review"

            # An unrecognised word whose form breaks a samāsa rule -- an
            # अव्ययीभाव with a case ending, महत्- where महा- is due -- gets that
            # specific, rule-cited note in place of the generic "not in the
            # lexicon" one. Only reached when nothing else was found -- no
            # lexicon hit and no spelling correction -- so it can neither hide
            # a confirmed error nor create one: it stays ⚪.
            samasa_issue = None
            if not is_valid and suggestion is None:
                ending = (self._avyayibhava_ending_issue(w_slp1)
                          or self._mahat_compound_issue(w_slp1))
                if ending:
                    status = "samasa_error"
                    suggestion, rule, samasa_issue = ending

            # An indeclinable's real grammatical identity is settled by the
            # lexicon match itself; a coincidental Kosha reading of the same
            # letters as some rare declinable noun is noise, not a competing
            # analysis, and must not feed case/gender agreement checks.
            is_avyaya = bool(analysis) and analysis.startswith("Avyaya")
            # A pronoun's grammatical role (puruSha/vacana/liNga) is already
            # fully determined by which तद्/अस्मद्/युष्मद् form was used
            # (PRONOUN_MAP / PRONOUN_GENDER_MAP), same as an avyaya. Bare
            # pronoun surfaces (ते, तत्, ...) frequently coincide with dozens
            # of unrelated noun-declension homographs in the Kosha (from
            # adjective stems ending the same way), so trusting those would
            # manufacture spurious case/gender conflicts for a word whose
            # real identity is not in question.
            is_pronoun = _pronoun_lookup(PRONOUN_MAP, w_slp1) is not None
            nominal_entries = []
            if not is_avyaya and not is_pronoun:
                nominal_entries = [
                    e for e in self._raw_kosha_entries(w_slp1)
                    if type(e).__name__.endswith("Subanta")
                ]
                # Words that exist only in the supplemental lexicon (e.g.
                # बालिका, अध्यापिका -- textbook stems vidyut's base Kosha does
                # not carry) still need structured vibhakti/vacana/liNga data
                # to participate in real case/gender agreement checking.
                lex_entry = self._lexicon.lookup(w_slp1)
                if lex_entry and lex_entry.subanta is not None:
                    nominal_entries.append(lex_entry.subanta)
            verb_readings = self._verb_grammar.lookup(w_slp1)

            tok = TokenResult(
                text_deva=w_deva,
                text_slp1=w_slp1,
                underlying_slp1=underlying_slp1,
                lemma=lemma,
                is_valid=is_valid,
                status=status,
                severity=severity,
                analysis=analysis,
                suggestion=suggestion,
                rule=rule,
                samasa_issue=samasa_issue,
                nominal_entries=nominal_entries,
                verb_readings=verb_readings,
                kosha_lookup=self._raw_kosha_entries,
            )
            result.tokens.append(tok)

        # 2. Check sandhi junctions between adjacent tokens
        for i in range(len(result.tokens) - 1):
            t1 = result.tokens[i]
            t2 = result.tokens[i + 1]

            # If t1 is a masculine a-stem written as bare stem (e.g. rAma without visarga/o)
            # and is followed by a word starting with voiced consonant, normalize underlying to 'as'
            underlying_w1 = t1.underlying_slp1
            # A masculine a-stem written without its visarga (राम for रामः)
            # is restored to -as so the junction can be judged. This must not
            # be applied to an अव्यय: an indeclinable has no case ending to
            # restore, so promoting न to नस् and then citing हशि च (६.१.११४)
            # to demand नो is inventing a विसर्ग the word never had. The rule
            # only ever applies to a pada that really ends in -अस्.
            #
            # The restoration is also skipped before a vowel other than short
            # अ, where it is not merely unnecessary but actively wrong-headed:
            # विसर्ग before such a vowel leaves no visible trace (अस् + इ is
            # simply "अ इ" with hiatus), so the promoted form yields no
            # advisory at all -- while it *blocks* the reading that does, the
            # गुण/वृद्धि/सवर्ण-दीर्घ junction of a bare stem with the next
            # word. Measured on the §4.9 cases: promoted, नर + इन्द्रः offers
            # nothing; bare, it offers नरेन्द्रः (आद्गुणः ६.१.८७), and
            # likewise सुरेशः and गणेशः. Short अ is deliberately kept on the
            # promotion path, because there the विसर्ग reading is the right
            # one -- राम + अपि is रामोऽपि (अतो रोरप्लुतादप्लुते ६.१.११३),
            # not the सवर्ण-दीर्घ रामापि a bare stem would suggest.
            next_is_non_a_vowel = (
                t2.underlying_slp1[:1] in ("A", "i", "I", "u", "U", "f", "F", "x", "X", "e", "E", "o", "O")
            )
            if (
                underlying_w1 == t1.text_slp1
                and underlying_w1.endswith("a")
                and not underlying_w1.endswith("va")
                and not next_is_non_a_vowel
                and not self._is_function_word(t1.text_slp1)
            ):
                if list(self._kosha.get(underlying_w1 + "s")) or self._lexicon.lookup(underlying_w1 + "s"):
                    underlying_w1 = underlying_w1 + "s"

            junction = self.check_sandhi_boundary(
                t1.text_slp1,
                t2.text_slp1,
                self._repha_base(underlying_w1),
                t2.underlying_slp1,
            )

            if junction.issue_detected and t1.status == "valid":
                # Writing padas unjoined across a word boundary is a legitimate
                # editorial convention in Sanskrit (padapATha-style), not a
                # defect in the word itself -- so this is offered at review
                # tier, never asserted as a confirmed error. Only escalate a
                # word already flagged invalid for its own sake stays that way.
                t1.status = "sandhi_error"
                t1.severity = "review"
                t1.suggestion = junction.suggested_w1_deva
                t1.rule = junction.rule_sutra
                t1.sandhi_issue = (
                    f"External sandhi not applied before '{t2.text_deva}': the "
                    f"expected sandhi-joined form is '{junction.suggested_w1_deva}' "
                    f"({junction.rule_explanation}). Writing the words unjoined is a "
                    f"legitimate editorial convention, so this is offered for a "
                    f"style decision rather than reported as an error."
                )

            # अनुस्वार written for a पदान्त म् before a *vowel*. मोऽनुस्वारः
            # (८.३.२३) is conditioned on हलि -- a following consonant -- so
            # शीघ्रं उत्तिष्ठति should keep its म्: शीघ्रम् उत्तिष्ठति. This is
            # decided by the spelling alone (a final anusvāra, a vowel next),
            # needs no analysis of either word, and is very common in modern
            # printing, so it is offered as a ⚪ note like the sandhi ones.
            # Only raised on a word with nothing else to say about it, so it
            # never displaces a sandhi note or an error.
            elif (t1.status == "valid" and t1.text_slp1.endswith("M")
                  and t2.text_slp1[:1] in _VOWELS):
                corrected = transliterate(t1.text_slp1[:-1] + "m", Scheme.Slp1, Scheme.Devanagari)
                t1.status = "sandhi_error"
                t1.severity = "review"
                t1.suggestion = corrected
                t1.rule = "मोऽनुस्वारः (८.३.२३)"
                t1.sandhi_issue = (
                    f"'{t1.text_deva}' is written with an anusvāra before the vowel of "
                    f"'{t2.text_deva}'. मोऽनुस्वारः (८.३.२३) replaces a पदान्त म् with "
                    f"अनुस्वार only before a consonant, so before a vowel the म् stays: "
                    f"'{corrected}'. Printed texts vary on this, so it is offered as a "
                    f"style point rather than reported as an error."
                )

        # 3. Phase 3: Syntactic, Kāraka Dependency, and Samāsa Analysis
        syntax_issues, compounds = self._karaka_engine.analyze_sentence(result.tokens)
        result.syntax_issues = syntax_issues
        result.compounds = compounds

        # Map syntax issues back to specific tokens
        for issue in syntax_issues:
            if 0 <= issue.token_index < len(result.tokens):
                tok = result.tokens[issue.token_index]
                # A confirmed grammar error outranks a review-tier note
                # already sitting on the same token. Sandhi runs first and
                # marks the *first* word of a junction, which is often the
                # very word an agreement issue lands on, so without this an
                # optional style suggestion silently hid a real error from
                # error_count / syntax_error_count.
                outranks_existing = (
                    tok.status != "valid"
                    and tok.severity == "review"
                    and issue.severity == "error"
                )
                if tok.status == "valid" or outranks_existing:
                    tok.status = issue.issue_type
                    tok.severity = issue.severity
                    tok.suggestion = issue.suggested_text
                    tok.rule = issue.rule_sutra
                    tok.karaka_issue = f"{issue.title}: {issue.description}"

        return result
