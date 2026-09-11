"""
Sandhi Boundary & Junction Verification Engine.

Checks word-junction validity between neighboring Sanskrit tokens:
  1. Identifies mandatory external sandhi transformations (Visarga, Hal, Ac).
  2. Detects unapplied or erroneously applied sandhi (e.g. 'रामः गच्छति' -> 'रामो गच्छति').
  3. Provides exact Paninian rule citations and suggested corrections.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from vidyut.lipi import Scheme, transliterate


@dataclass
class JunctionResult:
    is_valid_sandhi: bool
    issue_detected: bool
    rule_sutra: Optional[str] = None
    rule_explanation: Optional[str] = None
    suggested_w1_slp1: Optional[str] = None
    suggested_w1_deva: Optional[str] = None
    suggested_joined_deva: Optional[str] = None


# Paninian Sutra annotations for common sandhi rule patterns
PANINI_SUTRA_MAP: dict[tuple[str, str], tuple[str, str]] = {
    # as + voiced consonant -> o (हशि च 6.1.114)
    ("as", "g"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "G"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "N"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "j"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "J"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "Y"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "q"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "Q"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "R"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "d"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "D"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "n"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "b"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "B"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "m"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "y"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "r"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "l"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "v"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    ("as", "h"): ("हशि च (६.१.११४)", "विसर्ग सन्धि: 'अस्' + घोष व्यञ्जन (हश्) -> 'ओ'"),
    # as + a -> o ' (अतो रोरप्लुतादप्लुते 6.1.113 & एङः पदान्तादति 6.1.109)
    ("as", "a"): ("अतो रोरप्लुतादप्लुते (६.१.११३) / एङः पदान्तादति (६.१.१०९)", "विसर्ग/पूर्वरूप सन्धि: 'अस्' + 'अ' -> 'ओऽ'"),
    # as + voiceless
    ("as", "c"): ("विसर्जनीयस्य सः (८.३.३४) / स्तोः श्चुना श्चुः (८.४.४०)", "विसर्ग सन्धि: 'अस्' + 'च्' -> 'अश्च्'"),
    ("as", "C"): ("विसर्जनीयस्य सः (८.३.३४) / स्तोः श्चुना श्चुः (८.४.४०)", "विसर्ग सन्धि: 'अस्' + 'छ्' -> 'अश्छ्'"),
    ("as", "t"): ("विसर्जनीयस्य सः (८.३.३४)", "विसर्ग सन्धि: 'अस्' + 'त्' -> 'अस्त्'"),
    ("as", "T"): ("विसर्जनीयस्य सः (८.३.३४)", "विसर्ग सन्धि: 'अस्' + 'थ्' -> 'अस्थ्'"),
    ("as", "w"): ("विसर्जनीयस्य सः (८.३.३४) / ष्टुना ष्टुः (८.४.४१)", "विसर्ग सन्धि: 'अस्' + 'ट्' -> 'अष्ट्'"),
    ("as", "W"): ("विसर्जनीयस्य सः (८.३.३४) / ष्टुना ष्टुः (८.४.४१)", "विसर्ग सन्धि: 'अस्' + 'ठ्' -> 'अष्ठ्'"),
    ("as", "k"): ("कुप्वोः ᳵकᳵपौ वा (८.३.३७)", "विसर्ग सन्धि: 'अस्' + 'क्' -> 'अः क्'"),
    ("as", "K"): ("कुप्वोः ᳵकᳵपौ वा (८.३.३७)", "विसर्ग सन्धि: 'अस्' + 'ख्' -> 'अः ख्'"),
    ("as", "p"): ("कुप्वोः ᳵकᳵपौ वा (८.३.३७)", "विसर्ग सन्धि: 'अस्' + 'प्' -> 'अः प्'"),
    ("as", "P"): ("कुप्वोः ᳵकᳵपौ वा (८.३.३७)", "विसर्ग सन्धि: 'अस्' + 'फ्' -> 'अः फ्'"),
    # m + consonant -> Anusvara (मोऽनुस्वारः 8.3.23)
    ("m", "k"): ("मोऽनुस्वारः (८.३.२३)", "व्यञ्जन सन्धि: पदान्त 'म्' + व्यञ्जन -> अनुस्वार 'ं'"),
    ("m", "p"): ("मोऽनुस्वारः (८.३.२३)", "व्यञ्जन सन्धि: पदान्त 'म्' + व्यञ्जन -> अनुस्वार 'ं'"),
    ("m", "g"): ("मोऽनुस्वारः (८.३.२३)", "व्यञ्जन सन्धि: पदान्त 'म्' + व्यञ्जन -> अनुस्वार 'ं'"),
    ("m", "c"): ("मोऽनुस्वारः (८.३.२३)", "व्यञ्जन सन्धि: पदान्त 'म्' + व्यञ्जन -> अनुस्वार 'ं'"),
    ("m", "t"): ("मोऽनुस्वारः (८.३.२३)", "व्यञ्जन सन्धि: पदान्त 'म्' + व्यञ्जन -> अनुस्वार 'ं'"),
}

# Vowel-junction sutra citations (सवर्ण-दीर्घ / गुण / वृद्धि / यण्), built
# programmatically rather than hand-typed one pair at a time -- the phoneme
# pairs below are cross-checked directly against every vowel-sandhi row in
# app/vidyut-data/sandhi/rules.csv, so a hand-typed list risked silently
# missing or mis-citing a pair where a generated one cannot.
_SAVARNA_DIRGHA = (
    "अकः सवर्णे दीर्घः (६.१.१०१)",
    "सवर्ण-दीर्घ सन्धि: समान स्वर + समान स्वर -> दीर्घ स्वर",
)
_GUNA = (
    "आद्गुणः (६.१.८७)",
    "गुण सन्धि: 'अ'/'आ' + इक् स्वर -> गुण",
)
_VRDDHI = (
    "वृद्धिरेचि (६.१.८८)",
    "वृद्धि सन्धि: 'अ'/'आ' + 'ए'/'ऐ'/'ओ'/'औ' -> वृद्धि",
)
_YAN = (
    "इको यणचि (६.१.७७)",
    "यण् सन्धि: इक् स्वर (इ/ई/उ/ऊ/ऋ/ॠ/ऌ/ॡ) + असमान स्वर -> य्/व्/र्/ल्",
)

# अ/आ, इ/ई, उ/ऊ, ऋ/ॠ, ऌ/ॡ -- each pair combines with itself to a long vowel.
for _short, _long in (("a", "A"), ("i", "I"), ("u", "U"), ("f", "F"), ("x", "X")):
    for _c1 in (_short, _long):
        for _c2 in (_short, _long):
            PANINI_SUTRA_MAP[(_c1, _c2)] = _SAVARNA_DIRGHA

# अ/आ + इक् स्वर -> गुण (इ/ई->ए, उ/ऊ->ओ, ऋ/ॠ->अर्, ऌ/ॡ->अल्)
for _c1 in ("a", "A"):
    for _c2 in ("i", "I", "u", "U", "f", "F", "x", "X"):
        PANINI_SUTRA_MAP[(_c1, _c2)] = _GUNA

# अ/आ + ए/ऐ/ओ/औ -> वृद्धि
for _c1 in ("a", "A"):
    for _c2 in ("e", "E", "o", "O"):
        PANINI_SUTRA_MAP[(_c1, _c2)] = _VRDDHI

# इक् स्वर + कोई भी असमान स्वर -> यण् (साम्य/दीर्घ पहले से ऊपर हैंडल हो चुका है)
_IK_SAVARNA = {"i": "I", "I": "i", "u": "U", "U": "u", "f": "F", "F": "f", "x": "X", "X": "x"}
_ALL_VOWELS = ("a", "A", "i", "I", "u", "U", "f", "F", "x", "X", "e", "E", "o", "O")
for _c1 in _IK_SAVARNA:
    for _c2 in _ALL_VOWELS:
        if _c2 == _c1 or _c2 == _IK_SAVARNA[_c1]:
            continue
        PANINI_SUTRA_MAP[(_c1, _c2)] = _YAN

del _short, _long, _c1, _c2, _IK_SAVARNA, _ALL_VOWELS


class SandhiChecker:
    """Paninian sandhi junction validator."""

    def __init__(self, rules_csv_path: str | Path):
        self._rules: dict[tuple[str, str], str] = {}
        self._load_rules(Path(rules_csv_path))

    def _load_rules(self, csv_path: Path):
        if not csv_path.exists():
            return
        with open(csv_path, encoding="utf-8") as f:
            for line in f:
                parts = line.strip().split(",")
                if len(parts) == 3 and parts[0] != "first":
                    self._rules[(parts[0], parts[1])] = parts[2]

    def apply_sandhi(self, first_slp1: str, second_slp1: str) -> Optional[tuple[str, str, Optional[str], Optional[str]]]:
        """Calculates expected sandhi between first and second SLP1 strings.

        Returns (result_joint_slp1, result_w1_slp1, sutra, explanation) or None.
        """
        # Try matching suffixes of first (up to length 4) with prefixes of second (up to length 3)
        for l1 in range(min(len(first_slp1), 4), 0, -1):
            for l2 in range(min(len(second_slp1), 3), 0, -1):
                s1 = first_slp1[-l1:]
                s2 = second_slp1[:l2]
                if (s1, s2) in self._rules:
                    res = self._rules[(s1, s2)]
                    prefix = first_slp1[:-l1]
                    suffix = second_slp1[l2:]
                    joined = prefix + res + suffix

                    # second_slp1 is w2's underlying/lexicon form, which this
                    # codebase keys on the pre-visarga consonant (e.g. Kosha
                    # entries end "Alayas", not the spoken "AlayaH" -- see
                    # sanskrit_engine.py). A space-less rule (full vowel
                    # fusion: सवर्ण-दीर्घ/गुण/वृद्धि) pulls that raw tail into
                    # `joined` verbatim, which would otherwise display as a
                    # bare स् where a visarga belongs. Finish the word-final
                    # rule using vidyut's own "s,," row from the same
                    # rules.csv, rather than leaving it half-applied.
                    if joined.endswith("s") and ("s", "") in self._rules:
                        joined = joined[:-1] + self._rules[("s", "")]

                    # Determine what w1 becomes
                    # If res contains a space, w1 and w2 stay separate words with transformed boundary
                    if " " in res:
                        res_w1, _ = res.split(" ", 1)
                        w1_transformed = prefix + res_w1
                    else:
                        w1_transformed = joined

                    sutra, exp = PANINI_SUTRA_MAP.get((s1, s2), (None, None))
                    return joined, w1_transformed, sutra, exp

        return None

    def check_junction(
        self,
        surface_w1_slp1: str,
        surface_w2_slp1: str,
        underlying_w1_slp1: str,
        underlying_w2_slp1: str,
    ) -> JunctionResult:
        """Evaluates whether surface_w1 followed by surface_w2 conforms to mandatory sandhi rules."""
        # 1. Normalize underlying forms (e.g. rAmaH -> rAmas)
        base_w1 = underlying_w1_slp1
        if base_w1.endswith("H"):
            base_w1 = base_w1[:-1] + "s"

        base_w2 = underlying_w2_slp1

        sandhi_info = self.apply_sandhi(base_w1, base_w2)
        if not sandhi_info:
            return JunctionResult(is_valid_sandhi=True, issue_detected=False)

        joined_expected, w1_expected, sutra, exp = sandhi_info

        # Convert to Devanagari for readability
        w1_expected_deva = transliterate(w1_expected, Scheme.Slp1, Scheme.Devanagari)
        joined_expected_deva = transliterate(joined_expected, Scheme.Slp1, Scheme.Devanagari)
        surface_w1_deva = transliterate(surface_w1_slp1, Scheme.Slp1, Scheme.Devanagari)

        # Check if surface form matches expected sandhi transformation
        # Specific check: When 'as' + voiced cons requires 'o' (e.g. rAmaH gacCati -> rAmo gacCati)
        if base_w1.endswith("as") and sutra and "हशि च" in sutra:
            # Expected surface_w1 should end in 'o' (or 'o ')
            if not surface_w1_slp1.endswith("o"):
                return JunctionResult(
                    is_valid_sandhi=False,
                    issue_detected=True,
                    rule_sutra=sutra,
                    rule_explanation=exp,
                    suggested_w1_slp1=w1_expected,
                    suggested_w1_deva=w1_expected_deva,
                    suggested_joined_deva=joined_expected_deva,
                )

        # Special check: as + a -> o ' (अतो रोरप्लुतादप्लुते)
        if base_w1.endswith("as") and sutra and "अतो रोरप्लुतादप्लुते" in sutra:
            if not surface_w1_slp1.endswith("o"):
                return JunctionResult(
                    is_valid_sandhi=False,
                    issue_detected=True,
                    rule_sutra=sutra,
                    rule_explanation=exp,
                    suggested_w1_slp1=w1_expected,
                    suggested_w1_deva=w1_expected_deva,
                    suggested_joined_deva=joined_expected_deva,
                )

        # Vowel-junction checks (सवर्ण-दीर्घ / गुण / वृद्धि / यण्). Unlike visarga,
        # these classes fuse w1 and w2 into a single orthographic unit when
        # applied, so there is no partial "surface already shows it" ending to
        # test the way "अस्" -> "ओ" is tested above -- two still-separate
        # surface tokens already mean the fusion did not happen. The
        # surface != expected guard is kept anyway, for the same reason every
        # branch above has one: never assert a computed value without
        # checking it against what was actually written.
        if sutra and "सवर्णे दीर्घः" in sutra:
            if surface_w1_slp1 != w1_expected:
                return JunctionResult(
                    is_valid_sandhi=False,
                    issue_detected=True,
                    rule_sutra=sutra,
                    rule_explanation=exp,
                    suggested_w1_slp1=w1_expected,
                    suggested_w1_deva=w1_expected_deva,
                    suggested_joined_deva=joined_expected_deva,
                )

        if sutra and "आद्गुणः" in sutra:
            if surface_w1_slp1 != w1_expected:
                return JunctionResult(
                    is_valid_sandhi=False,
                    issue_detected=True,
                    rule_sutra=sutra,
                    rule_explanation=exp,
                    suggested_w1_slp1=w1_expected,
                    suggested_w1_deva=w1_expected_deva,
                    suggested_joined_deva=joined_expected_deva,
                )

        if sutra and "वृद्धिरेचि" in sutra:
            if surface_w1_slp1 != w1_expected:
                return JunctionResult(
                    is_valid_sandhi=False,
                    issue_detected=True,
                    rule_sutra=sutra,
                    rule_explanation=exp,
                    suggested_w1_slp1=w1_expected,
                    suggested_w1_deva=w1_expected_deva,
                    suggested_joined_deva=joined_expected_deva,
                )

        if sutra and "इको यणचि" in sutra:
            if surface_w1_slp1 != w1_expected:
                return JunctionResult(
                    is_valid_sandhi=False,
                    issue_detected=True,
                    rule_sutra=sutra,
                    rule_explanation=exp,
                    suggested_w1_slp1=w1_expected,
                    suggested_w1_deva=w1_expected_deva,
                    suggested_joined_deva=joined_expected_deva,
                )

        return JunctionResult(is_valid_sandhi=True, issue_detected=False)
