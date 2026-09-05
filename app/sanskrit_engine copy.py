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
from app.karaka_syntax import KarakaSyntaxEngine, SyntaxIssue, SamasaAnalysis


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

# Common phonetic/orthographic typing substitutions
ORTHOGRAPHIC_SUBSTITUTIONS = [
    ("Dy", "dy", "'द्य' (द् + य) should be used instead of 'ध्य' (ध् + य)"),
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


@dataclass
class TokenResult:
    text_deva: str          # the token in Devanagari, as written / segmented
    text_slp1: str          # the token in SLP1
    underlying_slp1: str    # normalized pada in SLP1 (e.g. rAmas for rAmaH)
    lemma: Optional[str]    # dictionary root/stem
    is_valid: bool          # True if recognized
    status: str = "valid"   # "valid" | "invalid" | "sandhi_error" | "karaka_error" | "agreement_error"
    analysis: Optional[str] = None
    suggestion: Optional[str] = None
    rule: Optional[str] = None
    sandhi_issue: Optional[str] = None
    karaka_issue: Optional[str] = None


@dataclass
class CheckResult:
    input_text: str
    tokens: list[TokenResult] = field(default_factory=list)
    syntax_issues: list[SyntaxIssue] = field(default_factory=list)
    compounds: list[SamasaAnalysis] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return sum(1 for t in self.tokens if t.status != "valid")

    @property
    def sandhi_error_count(self) -> int:
        return sum(1 for t in self.tokens if t.status == "sandhi_error")

    @property
    def syntax_error_count(self) -> int:
        return sum(
            1 for t in self.tokens if t.status in ["karaka_error", "agreement_error", "upapada_error"]
        )


class SanskritEngine:
    """Loads vidyut data, supplemental lexicon, sandhi rules, and Karaka/Syntax engine."""

    def __init__(self, data_dir: str | Path):
        data_dir = Path(data_dir)
        self._chedaka = Chedaka(str(data_dir))
        self._kosha = Kosha(str(data_dir / "kosha"))
        self._lexicon = SupplementalLexicon()
        self._sandhi_checker = SandhiChecker(data_dir / "sandhi" / "rules.csv")
        self._karaka_engine = KarakaSyntaxEngine()

    def _describe(self, entry) -> str:
        """User-friendly grammatical description of a kosha entry."""
        return str(entry)

    def _raw_check(self, slp1_word: str) -> tuple[bool, Optional[str], Optional[str], str]:
        """Internal helper to test word existence without triggering suggestions loop."""
        # 1. Supplemental lexicon check
        lex_entry = self._lexicon.lookup(slp1_word)
        if lex_entry:
            lemma_deva = transliterate(lex_entry.lemma, Scheme.Slp1, Scheme.Devanagari)
            return True, lemma_deva, lex_entry.analysis, lex_entry.text_slp1

        # 2. Direct Kosha lookup
        entries = list(self._kosha.get(slp1_word))
        if entries:
            first = entries[0]
            lemma = getattr(first, "lemma", None)
            lemma_deva = transliterate(lemma, Scheme.Slp1, Scheme.Devanagari) if lemma else None
            analysis = self._describe(first)
            if len(entries) > 1:
                analysis += f"  (+{len(entries) - 1} other possible analyses)"
            return True, lemma_deva, analysis, slp1_word

        # 3. Visarga normalization (-H -> -s, -r)
        if slp1_word.endswith("H"):
            stem = slp1_word[:-1]
            for ending in ["s", "r"]:
                cand = stem + ending
                lex_entry = self._lexicon.lookup(cand)
                if lex_entry:
                    lemma_deva = transliterate(lex_entry.lemma, Scheme.Slp1, Scheme.Devanagari)
                    return True, lemma_deva, lex_entry.analysis, cand
                entries = list(self._kosha.get(cand))
                if entries:
                    first = entries[0]
                    lemma = getattr(first, "lemma", None)
                    lemma_deva = transliterate(lemma, Scheme.Slp1, Scheme.Devanagari) if lemma else None
                    analysis = self._describe(first)
                    if len(entries) > 1:
                        analysis += f"  (+{len(entries) - 1} other possible analyses)"
                    return True, lemma_deva, analysis, cand

        # 4. -o ending normalization (-o -> -as)
        if slp1_word.endswith("o"):
            cand = slp1_word[:-1] + "as"
            lex_entry = self._lexicon.lookup(cand)
            if lex_entry:
                lemma_deva = transliterate(lex_entry.lemma, Scheme.Slp1, Scheme.Devanagari)
                return True, lemma_deva, lex_entry.analysis, cand
            entries = list(self._kosha.get(cand))
            if entries:
                first = entries[0]
                lemma = getattr(first, "lemma", None)
                lemma_deva = transliterate(lemma, Scheme.Slp1, Scheme.Devanagari) if lemma else None
                analysis = self._describe(first)
                if len(entries) > 1:
                    analysis += f"  (+{len(entries) - 1} other possible analyses)"
                return True, lemma_deva, analysis, cand

        # 5. Anusvara normalization (-M -> -m)
        if slp1_word.endswith("M"):
            cand = slp1_word[:-1] + "m"
            lex_entry = self._lexicon.lookup(cand)
            if lex_entry:
                lemma_deva = transliterate(lex_entry.lemma, Scheme.Slp1, Scheme.Devanagari)
                return True, lemma_deva, lex_entry.analysis, cand
            entries = list(self._kosha.get(cand))
            if entries:
                first = entries[0]
                lemma = getattr(first, "lemma", None)
                lemma_deva = transliterate(lemma, Scheme.Slp1, Scheme.Devanagari) if lemma else None
                analysis = self._describe(first)
                return True, lemma_deva, analysis, cand

        # 6. -r ending normalization (-r -> -s)
        if slp1_word.endswith("r"):
            cand = slp1_word[:-1] + "s"
            entries = list(self._kosha.get(cand))
            if entries:
                first = entries[0]
                lemma = getattr(first, "lemma", None)
                lemma_deva = transliterate(lemma, Scheme.Slp1, Scheme.Devanagari) if lemma else None
                analysis = self._describe(first)
                return True, lemma_deva, analysis, cand

        return False, None, None, slp1_word

    def check_word(
        self, slp1_word: str
    ) -> tuple[bool, Optional[str], Optional[str], str, Optional[str], Optional[str]]:
        """Look up an SLP1-encoded word in lexicon and check for corrections.

        Returns (is_valid, lemma, analysis, underlying_slp1, suggestion_deva, rule_citation).
        """
        is_valid, lemma_deva, analysis, underlying = self._raw_check(slp1_word)
        if is_valid:
            return True, lemma_deva, analysis, underlying, None, None

        # Check for grammatical substitution suggestions (e.g. gamati -> gacCati)
        if slp1_word in COMMON_GRAMMAR_SUGGESTIONS:
            sug_slp1, sutra, exp = COMMON_GRAMMAR_SUGGESTIONS[slp1_word]
            sug_deva = transliterate(sug_slp1, Scheme.Slp1, Scheme.Devanagari)
            return False, None, exp, slp1_word, sug_deva, sutra

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

            tok = TokenResult(
                text_deva=w_deva,
                text_slp1=w_slp1,
                underlying_slp1=underlying_slp1,
                lemma=lemma,
                is_valid=is_valid,
                status=status,
                analysis=analysis,
                suggestion=suggestion,
                rule=rule,
            )
            result.tokens.append(tok)

        # 2. Check sandhi junctions between adjacent tokens
        for i in range(len(result.tokens) - 1):
            t1 = result.tokens[i]
            t2 = result.tokens[i + 1]

            # If t1 is a masculine a-stem written as bare stem (e.g. rAma without visarga/o)
            # and is followed by a word starting with voiced consonant, normalize underlying to 'as'
            underlying_w1 = t1.underlying_slp1
            if underlying_w1 == t1.text_slp1 and underlying_w1.endswith("a") and not underlying_w1.endswith("va"):
                if list(self._kosha.get(underlying_w1 + "s")) or self._lexicon.lookup(underlying_w1 + "s"):
                    underlying_w1 = underlying_w1 + "s"

            junction = self.check_sandhi_boundary(
                t1.text_slp1,
                t2.text_slp1,
                underlying_w1,
                t2.underlying_slp1,
            )

            if junction.issue_detected:
                t1.status = "sandhi_error"
                t1.suggestion = junction.suggested_w1_deva
                t1.rule = junction.rule_sutra
                t1.sandhi_issue = (
                    f"Required Sandhi transformation missing before '{t2.text_deva}': "
                    f"expected '{junction.suggested_w1_deva}' ({junction.rule_explanation})"
                )

        # 3. Phase 3: Syntactic, Kāraka Dependency, and Samāsa Analysis
        syntax_issues, compounds = self._karaka_engine.analyze_sentence(result.tokens)
        result.syntax_issues = syntax_issues
        result.compounds = compounds

        # Map syntax issues back to specific tokens
        for issue in syntax_issues:
            if 0 <= issue.token_index < len(result.tokens):
                tok = result.tokens[issue.token_index]
                if tok.status == "valid":
                    tok.status = issue.issue_type
                    tok.suggestion = issue.suggested_text
                    tok.rule = issue.rule_sutra
                    tok.karaka_issue = f"{issue.title}: {issue.description}"

        return result
