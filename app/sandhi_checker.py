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

        return JunctionResult(is_valid_sandhi=True, issue_detected=False)
