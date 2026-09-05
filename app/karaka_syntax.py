"""
Phase 3: Syntactic, Kāraka Dependency, and Samāsa Analysis Engine.

Performs sentence-level grammar checks:
  1. Verb-Argument Government (Kāraka / कारक-नियम):
     - Transitive verbs requiring Karma Kāraka (Dvitiyā) (e.g. भगवान् भक्तान् रक्षति).
     - Upapada vibhaktis (Caturthī for नमः/रुच्/दा, Tṛtīyā for सह/अलम्, Pañcamī for भी/त्रा).
  2. Subject-Verb Agreement (कर्तृ-क्रिया-अन्वय):
     - Puruṣa agreement (अहम् -> पठामि, त्वम् -> पठसि).
     - Vacana agreement (बालकाः -> पठन्ति, बालकौ -> पठतः).
  3. Compound (Samāsa) recognition and structural decomposition.
"""

from dataclasses import dataclass, field
from typing import Optional

from vidyut.lipi import Scheme, transliterate
from vidyut.prakriya import (
    Vyakarana,
    Pratipadika,
    Linga,
    Vibhakti,
    Vacana,
    Purusha,
    Pada,
)

from app.verb_grammar import VerbGrammar


def _pronoun_lookup(table: dict, slp1_word: str):
    """Look up a pronoun by surface form, accepting either spelling of a
    final म्: halant (अहम् -> "aham") or anusvara (अहं -> "ahaM"). Both are
    the same word -- अनुस्वार is simply how final म् is conventionally
    written before a following consonant -- so a table keyed on only one
    spelling would silently misread the other as an unrelated nominal."""
    if slp1_word in table:
        return table[slp1_word]
    if slp1_word.endswith("m"):
        alt = slp1_word[:-1] + "M"
    elif slp1_word.endswith("M"):
        alt = slp1_word[:-1] + "m"
    else:
        alt = None
    return table.get(alt) if alt else None


@dataclass
class SyntaxIssue:
    token_index: int
    token_text: str
    issue_type: str        # "karaka_error" | "agreement_error" | "upapada_error"
    title: str
    description: str
    suggested_text: Optional[str] = None
    rule_sutra: Optional[str] = None


@dataclass
class SamasaAnalysis:
    compound_text: str
    compound_type: str
    vigraha_vakya: str
    components: list[str]


# Knowledge base of transitive verbs and their required cases
TRANSITIVE_DHATU_MAP: dict[str, str] = {
    "rakz": "रक्ष् (to protect)",
    "paW": "पठ् (to read)",
    "gam": "गम् (to go)",
    "KAd": "खाद् (to eat)",
    "liK": "लिख् (to write)",
    "pA": "पा (to drink)",
    "dfS": "दृश् / पश्य् (to see)",
    "tyaj": "त्यज् (to abandon)",
    "sev": "सेव् (to serve)",
    "kf": "कृ (to do)",
    "nI": "नी (to lead)",
    "Dfv": "धृ (to hold)",
    "han": "हन् (to slay)",
    "smar": "स्मृ (to remember)",
}

# Verbs requiring Caturthī (Sampradāna)
CATURTHI_DHATU_MAP: dict[str, tuple[str, str]] = {
    "ruc": ("रुच्यर्थानां प्रीयमाणः (१.४.३२)", "धातु 'रुच्' (रोचते) requires चतुर्थी (Recipient / प्रीयमाण)"),
    "dA": ("कर्मणा यमभिप्रेति स सम्प्रदानम् (१.४.३२)", "धातु 'दा / यच्छ्' (ददाति / यच्छति) requires चतुर्थी (सम्प्रदान)"),
    "yacC": ("कर्मणा यमभिप्रेति स सम्प्रदानम् (१.४.३२)", "धातु 'यच्छ्' requires चतुर्थी (सम्प्रदान)"),
    "kruD": ("क्रुधद्रुहेर्ष्यासूयार्थानां यं प्रति कोपः (१.४.३७)", "धातु 'क्रुध्' (क्रुध्यति) requires चतुर्थी"),
    "kup": ("क्रुधद्रुहेर्ष्यासूयार्थानां यं प्रति कोपः (१.४.३७)", "धातु 'कुप्' (कुप्यति) requires चतुर्थी"),
    "Irzy": ("क्रुधद्रुहेर्ष्यासूयार्थानां यं प्रति कोपः (१.४.३७)", "धातु 'ईर्ष्य्' requires चतुर्थी"),
}

# Verbs requiring Pañcamī (Apādāna)
PANCHAMI_DHATU_MAP: dict[str, tuple[str, str]] = {
    "BI": ("भीत्रार्थानां भयहेतुः (१.४.२५)", "धातु 'भी' (बिभेति) requires पञ्चमी (भयहेतु)"),
    "trA": ("भीत्रार्थानां भयहेतुः (१.४.२५)", "धातु 'त्रा' (त्रायते) requires पञ्चमी"),
    "pramad": ("जुगुप्साविरामप्रमादार्थानामुपसंख्यानम् (१.४.२४)", "धातु 'प्रमद्' (प्रमाद्यति) requires पञ्चमी"),
}

# Upapadas requiring specific vibhaktis
UPAPADA_VIBHAKTI_MAP: dict[str, tuple[str, str, str]] = {
    "namaH": ("Caturthi", "नमःस्वस्तिस्वाहास्वधालंवषड्योगाच्च (२.३.२८)", "'नमः' requires चतुर्थी विभक्ति"),
    "namas": ("Caturthi", "नमःस्वस्तिस्वाहास्वधालंवषड्योगाच्च (२.३.२८)", "'नमः' requires चतुर्थी विभक्ति"),
    "svasti": ("Caturthi", "नमःस्वस्तिस्वाहास्वधालंवषड्योगाच्च (२.३.२८)", "'स्वस्ति' requires चतुर्थी विभक्ति"),
    "saha": ("Trtiya", "सहयुक्तेऽप्रधाने (२.३.१९)", "'सह' requires तृतीया विभक्ति"),
    "sAkam": ("Trtiya", "सहयुक्तेऽप्रधाने (२.३.१९)", "'साकम्' requires तृतीया विभक्ति"),
    "sArDam": ("Trtiya", "सहयुक्तेऽप्रधाने (२.३.१९)", "'सार्धम्' requires तृतीया विभक्ति"),
    "vinA": ("Dvitiya_Trtiya_Panchami", "पृथग्विनानानाभिस्तृतीयाऽन्यतरस्याम् (२.३.३२)", "'विना' requires द्वितीया, तृतीया, or पञ्चमी"),
    "vina": ("Dvitiya_Trtiya_Panchami", "पृथग्विनानानाभिस्तृतीयाऽन्यतरस्याम् (२.३.३२)", "'विना' requires द्वितीया, तृतीया, or पञ्चमी"),
    "alam": ("Trtiya", "अलमिति प्रतिषेधार्थे तृतीया", "'अलम्' (निषेधार्थे) requires तृतीया विभक्ति"),
    "bahiH": ("Panchami", "अपादाने पञ्चमी (२.३.२८)", "'बहिः' requires पञ्चमी विभक्ति"),
}

# Pronoun person-number registry
PRONOUN_MAP: dict[str, tuple[str, str]] = {
    # 1st Person (अस्मद्)
    "aham": ("Uttama", "Eka"),
    "AvAm": ("Uttama", "Dvi"),
    "vayam": ("Uttama", "Bahu"),
    # 2nd Person (युष्मद्)
    "tvam": ("Madhyama", "Eka"),
    "yuvAm": ("Madhyama", "Dvi"),
    "yUyam": ("Madhyama", "Bahu"),
    # 3rd Person (तद्, एतद्, etc.)
    "saH": ("Prathama", "Eka"),
    "sas": ("Prathama", "Eka"),
    "sa": ("Prathama", "Eka"),
    "tO": ("Prathama", "Dvi"),
    "te": ("Prathama", "Bahu"),
    "sA": ("Prathama", "Eka"),
    "tAH": ("Prathama", "Bahu"),
    "tat": ("Prathama", "Eka"),
    "tAni": ("Prathama", "Bahu"),
    "ezaH": ("Prathama", "Eka"),
    "ezas": ("Prathama", "Eka"),
    "eza": ("Prathama", "Eka"),
    "ete": ("Prathama", "Bahu"),
    "etad": ("Prathama", "Eka"),
    "ezA": ("Prathama", "Eka"),
}

# तद्/एतद् pronoun liNga (gender) by surface form -- a closed paradigm, like
# PRONOUN_MAP above, used only to check pronoun-noun gender agreement.
PRONOUN_GENDER_MAP: dict[str, str] = {
    "saH": "Pum", "sas": "Pum", "sa": "Pum",
    "sA": "Stri",
    "tat": "Napumsaka",
    "ezaH": "Pum", "ezas": "Pum", "eza": "Pum",
    "ezA": "Stri",
    "etad": "Napumsaka",
}

# Well-known Sanskrit compounds database
KNOWN_SAMASAS: dict[str, SamasaAnalysis] = {
    "rAjapuruzaH": SamasaAnalysis(
        compound_text="राजपुरुषः",
        compound_type="षष्ठी-तत्पुरुष-समासः (Sasthi-Tatpurusha)",
        vigraha_vakya="राज्ञः पुरुषः",
        components=["राजन्", "पुरुष"],
    ),
    "vidyAlayaH": SamasaAnalysis(
        compound_text="विद्यालयः",
        compound_type="षष्ठी-तत्पुरुष-समासः (Sasthi-Tatpurusha)",
        vigraha_vakya="विद्यायाः आलयः",
        components=["विद्या", "आलय"],
    ),
    "pItAmbaraH": SamasaAnalysis(
        compound_text="पीताम्बरः",
        compound_type="बहुव्रीहि-समासः (Bahuvrihi)",
        vigraha_vakya="पीतं अम्बरं यस्य सः (श्रीकृष्णः/विष्णुः)",
        components=["पीत", "अम्बर"],
    ),
    "mahApuruzaH": SamasaAnalysis(
        compound_text="महापुरुषः",
        compound_type="कर्मधारय-समासः (Karmadharaya)",
        vigraha_vakya="महान् चासौ पुरुषः",
        components=["महत्", "पुरुष"],
    ),
    "daSaraTaputraH": SamasaAnalysis(
        compound_text="दशरथपुत्रः",
        compound_type="षष्ठी-तत्पुरुष-समासः (Sasthi-Tatpurusha)",
        vigraha_vakya="दशरथस्य पुत्रः",
        components=["दशरथ", "पुत्र"],
    ),
    "satsaNgadIkzA": SamasaAnalysis(
        compound_text="सत्सङ्गदीक्षा",
        compound_type="षष्ठी-तत्पुरुष-समासः (Sasthi-Tatpurusha)",
        vigraha_vakya="सत्सङ्गस्य दीक्षा",
        components=["सत्सङ्ग", "दीक्षा"],
    ),
}


class KarakaSyntaxEngine:
    """Performs Kāraka dependency verification, Subject-Verb agreement, and Samāsa analysis."""

    def __init__(self, verb_grammar: Optional[VerbGrammar] = None):
        self._vyakarana = Vyakarana()
        self._verb_grammar = verb_grammar

    # -- structured-grammar helpers -----------------------------------------
    #
    # These replace string-matching on a stringified Kosha description and
    # ad hoc stem+suffix concatenation with the actual grammatical categories
    # vidyut attaches to a recognised word, and with genuine re-derivation via
    # vidyut.prakriya (Vyakarana.derive) for any case/number/root the analysis
    # needs to check -- so results are correct for every stem class (a-stem,
    # u-stem, r-stem, consonant stem, ...), not only the ones a suffix rule
    # happened to cover.

    @staticmethod
    def _rank_nominal_entries(entries: list) -> list:
        """Order a token's candidate nominal readings, most-likely first.

        A surface form can be genuinely ambiguous in the Kosha (e.g. रामः
        also matches a rare कृदन्त bahuvacana reading of the unrelated root
        रम्, alongside the ordinary proper-noun reading). vidyut does not
        rank these by frequency, so an ordinary/basic nominal stem is
        preferred over a secondary (कृदन्त-derived) formation whenever both
        are available for the same surface form.
        """
        def rank(e):
            kind = type(e.pratipadika_entry).__name__
            return 0 if kind.endswith("Basic") else 1
        return sorted(entries, key=rank)

    def _case_form(self, nominal_entries: list, vibhakti, vacana=None) -> Optional[str]:
        """Derive a token's own praatipadika in a different vibhakti/vacana.

        Re-derives the requested subanta form via Vyakarana on the same
        pratipadika and linga vidyut already recognised for this token, so
        the result is correct for the word's actual declension class
        instead of a generic (and frequently wrong) stem+suffix guess.
        """
        if not nominal_entries:
            return None
        entry = self._rank_nominal_entries(nominal_entries)[0]
        try:
            args = entry.to_prakriya_args()
            sub = Pada.Subanta(
                pratipadika=args.pratipadika,
                linga=args.linga,
                vibhakti=vibhakti,
                vacana=vacana or args.vacana,
            )
            forms = sorted({r.text for r in self._vyakarana.derive(sub)})
            return forms[0] if forms else None
        except Exception:
            return None

    def _has_vibhakti(self, nominal_entries: list, vibhakti) -> bool:
        return any(e.vibhakti == vibhakti for e in nominal_entries)

    def _entry_vacana(self, nominal_entries: list) -> Optional[object]:
        """The vacana of a token's most-likely nominal reading (see _rank_nominal_entries)."""
        if not nominal_entries:
            return None
        return self._rank_nominal_entries(nominal_entries)[0].vacana

    def _prathama_lingas(self, tok) -> set:
        """The liNga(s) a token can carry when read as a Prathama-vibhakti
        nominal (subject/predicate-nominative position) -- from the तद्/एतद्
        pronoun paradigm, or from vidyut's own Subanta entries. Neuter nouns
        are not included via nominal_entries unless genuinely Prathama (their
        प्रथमा and द्वितीया happen to coincide, so this alone cannot
        distinguish subject from object; callers must only use this where
        no governing verb makes that distinction necessary)."""
        gender = _pronoun_lookup(PRONOUN_GENDER_MAP, tok.text_slp1)
        if gender is not None:
            return {gender}
        # A bare stem with no case ending at all (e.g. देव written plain,
        # about to combine with a following word into देवेन्द्रः) is not a
        # standalone Prathama nominal -- vidyut's Kosha can still surface a
        # Prathama-tagged homograph for the bare stem, but trusting it here
        # would call every unsandhied vowel-junction compound a gender clash.
        # H/m/M: masc./fem. visarga or neuter anusvara endings. A/I: feminine
        # A-stem and I-stem nominatives (बालिका, सुन्दरी, नदी, ...), which
        # never take a visarga at all, so their bare ending is already a
        # genuine case marker, not a stem fragment.
        if not tok.text_slp1.endswith(("H", "m", "M", "A", "I")):
            return set()
        prathama_entries = [e for e in tok.nominal_entries if e.vibhakti == Vibhakti.Prathama]
        if not prathama_entries:
            return set()
        # Same precedence as _rank_nominal_entries: an ordinary/basic nominal
        # reading is preferred over a rarer secondary (कृदन्त-derived)
        # formation. Only the single best-ranked reading's liNga is used
        # (not a union across every same-rank homograph): vidyut's Kosha can
        # carry several unrelated Basic pratipadikas under one bare surface
        # key (e.g. नदी also matching an unrelated masculine/neuter proper
        # noun), and unioning them back in would make almost any liNga
        # "possible" for almost any word, defeating the check.
        return {self._rank_nominal_entries(prathama_entries)[0].linga.name}

    def _identify_dhatu_hint(self, verb_readings: list, hint_map: dict, fallback_slp1: str) -> Optional[str]:
        """Find which lexical dhatu-hint (a key of hint_map) names this verb's
        actual root, preferring the root vidyut's own derivation engine
        identified (verb_readings) over surface-string prefix matching, which
        breaks for any verb class with reduplication or guna/vrddhi changes
        (e.g. ददाति from दा does not start with 'dA')."""
        if self._verb_grammar and verb_readings:
            codes = {vf.dhatu_code for vf in verb_readings}
            for hint in hint_map:
                if any(self._verb_grammar.root_matches(code, hint) for code in codes):
                    return hint
        for hint in hint_map:
            if fallback_slp1.startswith(hint):
                return hint
        return None

    def analyze_sentence(self, tokens: list) -> tuple[list[SyntaxIssue], list[SamasaAnalysis]]:
        """Analyzes a sequence of token results for syntactic/kāraka issues."""
        issues: list[SyntaxIssue] = []
        compounds: list[SamasaAnalysis] = []

        if not tokens:
            return issues, compounds

        # 1. Samāsa analysis for each token
        for i, t in enumerate(tokens):
            slp1 = t.text_slp1
            if slp1.endswith("s") or slp1.endswith("r"):
                slp1 = slp1[:-1] + "H"
            if slp1 in KNOWN_SAMASAS:
                compounds.append(KNOWN_SAMASAS[slp1])

        # 2. Extract verbs, nouns, pronouns, and upapadas.
        # A verb is primarily identified by a genuine Paninian derivation
        # match (verb_readings, from VerbGrammar) -- this covers every root
        # in the Dhatupatha, not a fixed list of surface forms. The old
        # string/list heuristic remains only as a fallback for lakaras
        # VerbGrammar does not index (it covers लट्-कर्तरि only).
        verb_indices = []
        for i, t in enumerate(tokens):
            analysis_str = t.analysis or ""
            t_slp1 = t.text_slp1
            if (
                t.verb_readings
                or "Tinanta" in analysis_str
                or "तिङन्त" in analysis_str
                or "Lakara" in analysis_str
                or t_slp1 in ["paWati", "gacCati", "pibati", "rakzati", "KAdati", "paSyati", "paWanti", "gacCanti", "pibanti", "rakzanti", "paWasi", "gacCasi", "paWAmi", "gacCAmi"]
            ):
                verb_indices.append(i)

        # 3. Kāraka & Verb-Argument Government Checking
        for v_idx in verb_indices:
            v_tok = tokens[v_idx]
            v_slp1 = v_tok.text_slp1
            v_analysis = v_tok.analysis or ""

            # Determine root/dhatu: prefer the root vidyut's own derivation
            # engine identified for this exact surface form over prefix
            # matching, which is wrong for any verb class with reduplication
            # or a guna/vrddhi-altered stem (e.g. ददाति from दा does not
            # start with "dA").
            dhatu_clean = self._identify_dhatu_hint(v_tok.verb_readings, TRANSITIVE_DHATU_MAP, v_slp1)
            if dhatu_clean is None and "rakz" in v_slp1 and "rakz" in TRANSITIVE_DHATU_MAP:
                dhatu_clean = "rakz"

            # Check Transitive Root requiring Dvitiyā (Karma Kāraka)
            if dhatu_clean and dhatu_clean in TRANSITIVE_DHATU_MAP:
                for n_idx in range(v_idx):
                    n_tok = tokens[n_idx]
                    n_analysis = n_tok.analysis or ""
                    n_slp1 = n_tok.text_slp1

                    is_sasthi = (
                        self._has_vibhakti(n_tok.nominal_entries, Vibhakti.Sasthi)
                        if n_tok.nominal_entries else
                        ("Sasthi" in n_analysis or "षष्ठी" in n_analysis or n_slp1.endswith("AnAm")
                         or n_slp1.endswith("ARAm") or n_slp1.endswith("asya"))
                    )
                    if is_sasthi:
                        is_plural = self._entry_vacana(n_tok.nominal_entries) == Vacana.Bahu
                        dvitiya_slp1 = self._case_form(n_tok.nominal_entries, Vibhakti.Dvitiya)
                        if dvitiya_slp1 is None:
                            continue  # no grammatically verified correction available
                        dvitiya_deva = transliterate(dvitiya_slp1, Scheme.Slp1, Scheme.Devanagari)

                        issues.append(
                            SyntaxIssue(
                                token_index=n_idx,
                                token_text=n_tok.text_deva,
                                issue_type="karaka_error",
                                title="Kāraka / Case Government Error (कर्मकारक-विभक्ति-दोषः)",
                                description=(
                                    f"धातु '{TRANSITIVE_DHATU_MAP[dhatu_clean]}' is transitive (सकर्मक) "
                                    f"and requires direct object in Dvitiyā vibhakti (कर्मणि द्वितीया), "
                                    f"not Ṣaṣṭhī (षष्ठी विभक्तिः)."
                                ),
                                suggested_text=dvitiya_deva,
                                rule_sutra="कर्मणि द्वितीया (२.३.२) / कर्तुरीप्सिततमं कर्म (१.४.४९)",
                            )
                        )

            # Check Caturthī Dhatu requirement (e.g. ruc, dA, kruD)
            caturthi_hint = self._identify_dhatu_hint(v_tok.verb_readings, CATURTHI_DHATU_MAP, v_slp1)
            if caturthi_hint:
                sutra, desc = CATURTHI_DHATU_MAP[caturthi_hint]
                for n_idx in range(v_idx):
                    n_tok = tokens[n_idx]
                    n_analysis = n_tok.analysis or ""
                    n_slp1 = n_tok.text_slp1
                    is_sasthi = (
                        self._has_vibhakti(n_tok.nominal_entries, Vibhakti.Sasthi)
                        if n_tok.nominal_entries else
                        ("Sasthi" in n_analysis or "षष्ठी" in n_analysis or n_slp1.endswith("asya"))
                    )
                    if is_sasthi:
                        caturthi_slp1 = self._case_form(n_tok.nominal_entries, Vibhakti.Caturthi)
                        if caturthi_slp1 is None:
                            continue
                        caturthi_deva = transliterate(caturthi_slp1, Scheme.Slp1, Scheme.Devanagari)
                        issues.append(
                            SyntaxIssue(
                                token_index=n_idx,
                                token_text=n_tok.text_deva,
                                issue_type="karaka_error",
                                title="Sampradāna Kāraka Error (सम्प्रदान-कारक-दोषः)",
                                description=desc,
                                suggested_text=caturthi_deva,
                                rule_sutra=sutra,
                            )
                        )

            # Check Pañcamī Dhatu requirement (e.g. BI -> bibheti)
            panchami_hint = self._identify_dhatu_hint(v_tok.verb_readings, PANCHAMI_DHATU_MAP, v_slp1)
            if panchami_hint is None and "biBe" in v_slp1 and "BI" in PANCHAMI_DHATU_MAP:
                panchami_hint = "BI"
            if panchami_hint:
                sutra, desc = PANCHAMI_DHATU_MAP[panchami_hint]
                for n_idx in range(v_idx):
                    n_tok = tokens[n_idx]
                    n_analysis = n_tok.analysis or ""
                    n_slp1 = n_tok.text_slp1
                    is_sasthi = (
                        self._has_vibhakti(n_tok.nominal_entries, Vibhakti.Sasthi)
                        if n_tok.nominal_entries else
                        ("Sasthi" in n_analysis or "षष्ठी" in n_analysis or n_slp1.endswith("asya"))
                    )
                    if is_sasthi:
                        panchami_slp1 = self._case_form(n_tok.nominal_entries, Vibhakti.Panchami)
                        if panchami_slp1 is None:
                            continue
                        panchami_deva = transliterate(panchami_slp1, Scheme.Slp1, Scheme.Devanagari)
                        issues.append(
                            SyntaxIssue(
                                token_index=n_idx,
                                token_text=n_tok.text_deva,
                                issue_type="karaka_error",
                                title="Apādāna Kāraka Error (अपादान-कारक-दोषः)",
                                description=desc,
                                suggested_text=panchami_deva,
                                rule_sutra=sutra,
                            )
                        )

        # 4. Upapada Vibhakti Checking (e.g. devasya namaH -> devAya namaH)
        for i, t in enumerate(tokens):
            t_slp1 = t.text_slp1
            if t_slp1 in UPAPADA_VIBHAKTI_MAP and i > 0:
                req_vib, sutra, desc = UPAPADA_VIBHAKTI_MAP[t_slp1]
                prev_tok = tokens[i - 1]
                prev_ana = prev_tok.analysis or ""
                prev_slp1 = prev_tok.text_slp1
                is_sasthi = (
                    self._has_vibhakti(prev_tok.nominal_entries, Vibhakti.Sasthi)
                    if prev_tok.nominal_entries else
                    ("Sasthi" in prev_ana or "षष्ठी" in prev_ana or prev_slp1.endswith("asya"))
                )
                if req_vib == "Caturthi" and is_sasthi:
                    sug_slp1 = self._case_form(prev_tok.nominal_entries, Vibhakti.Caturthi)
                    if sug_slp1 is None:
                        continue
                    sug_deva = transliterate(sug_slp1, Scheme.Slp1, Scheme.Devanagari)
                    issues.append(
                        SyntaxIssue(
                            token_index=i - 1,
                            token_text=prev_tok.text_deva,
                            issue_type="upapada_error",
                            title="Upapada Vibhakti Error (उपपद-विभक्ति-दोषः)",
                            description=desc,
                            suggested_text=sug_deva,
                            rule_sutra=sutra,
                        )
                    )

        # 5. Gender (liNga) agreement in bare nominal apposition ("sundaraH
        # bAlikA", "saH bAlikA asti"). Deliberately narrow: it only runs when
        # the sentence has no *action* verb governing an object (a real
        # action verb's object is frequently a neuter noun whose प्रथमा and
        # द्वितीया coincide, which would make this indistinguishable from a
        # genuine subject -- so outside a copula-only/verbless sentence,
        # liNga agreement between adjacent nominals cannot be judged safely
        # without also resolving kAraka roles, which risks exactly the false
        # positives this design otherwise avoids).
        has_action_verb = any(
            not (
                v.verb_readings
                and all(self._verb_grammar and self._verb_grammar.root_matches(vf.dhatu_code, "as") for vf in v.verb_readings)
            )
            for v in (tokens[i] for i in verb_indices)
        )
        if not has_action_verb:
            for i in range(len(tokens) - 1):
                a = tokens[i]
                j = i + 1
                if j in verb_indices:  # skip over a copula between the two nominals
                    j += 1
                if j >= len(tokens) or j in verb_indices:
                    continue
                b = tokens[j]
                a_lingas = self._prathama_lingas(a)
                b_lingas = self._prathama_lingas(b)
                if a_lingas and b_lingas and not (a_lingas & b_lingas):
                    issues.append(
                        SyntaxIssue(
                            token_index=i,
                            token_text=a.text_deva,
                            issue_type="agreement_error",
                            title="Gender Agreement Error (लिङ्ग-अन्वय-दोषः)",
                            description=(
                                f"'{a.text_deva}' ({'/'.join(sorted(a_lingas))}) does not agree in "
                                f"liNga with '{b.text_deva}' ({'/'.join(sorted(b_lingas))})."
                            ),
                            suggested_text=None,
                            rule_sutra="विशेषणं विशेष्येण बहुलम् (विशेषण-विशेष्य-लिङ्ग-अन्वयः)",
                        )
                    )

        # 6. Subject-Verb Agreement Checking (Puruṣa & Vacana Anvaya)
        #
        # Primary path: both the subject's (puruSha, vacana) and the verb's
        # actual (puruSha, vacana) are read from real grammatical categories
        # -- vidyut.kosha's Subanta entries for the subject, VerbGrammar's
        # Paninian-derived tiNanta index for the verb -- and any mismatch's
        # correction is *derived* (Vyakarana on the verb's own dhatu), not
        # assembled by string surgery. This uniformly covers puruSha, vacana
        # and dvivacana in one mechanism instead of separate ad hoc branches.
        if tokens and verb_indices:
            first_verb_idx = verb_indices[0]
            v_tok = tokens[first_verb_idx]
            v_ana = v_tok.analysis or ""
            v_slp1 = v_tok.text_slp1

            # Identify subject candidate among preceding tokens: a known
            # pronoun, or a nominal with a genuine Prathama reading, falling
            # back to the surface-ending heuristic only when vidyut supplied
            # no structured reading at all for this token.
            subj_tok = None
            for idx in range(first_verb_idx):
                t = tokens[idx]
                t_slp1 = t.text_slp1
                t_ana = t.analysis or ""
                if _pronoun_lookup(PRONOUN_MAP, t_slp1) is not None or self._has_vibhakti(t.nominal_entries, Vibhakti.Prathama):
                    subj_tok = t
                    break
                if not t.nominal_entries and (
                    "Prathama" in t_ana or "प्रथमा" in t_ana
                    or t_slp1.endswith("AH") or t_slp1.endswith("as") or t_slp1.endswith("aH")
                    or t_slp1.endswith("o") or t_slp1.endswith("An")
                ):
                    subj_tok = t
                    break

            if subj_tok:
                s_slp1 = subj_tok.text_slp1

                pronoun_hit = _pronoun_lookup(PRONOUN_MAP, s_slp1)
                if pronoun_hit is not None:
                    purusha_name, vacana_name = pronoun_hit
                    subj_purusha = getattr(Purusha, purusha_name)
                    subj_vacana = getattr(Vacana, vacana_name)
                else:
                    subj_purusha = Purusha.Prathama  # a nominal subject is always grammatically 3rd person
                    subj_vacana = self._entry_vacana(subj_tok.nominal_entries) or (
                        Vacana.Bahu if s_slp1.endswith("AH") or s_slp1 in ["te", "tAH", "tAni", "ete"] else Vacana.Eka
                    )

                agrees = any(
                    vf.purusha == subj_purusha and vf.vacana == subj_vacana
                    for vf in v_tok.verb_readings
                )

                if v_tok.verb_readings and not agrees and self._verb_grammar:
                    dhatu_code = v_tok.verb_readings[0].dhatu_code
                    corrected = sorted(self._verb_grammar.suggest(dhatu_code, subj_purusha, subj_vacana))
                    if corrected:
                        sug_verb_deva = transliterate(corrected[0], Scheme.Slp1, Scheme.Devanagari)
                        actual = v_tok.verb_readings[0]
                        title, rule_sutra = _agreement_title_and_rule(subj_purusha, actual.purusha != subj_purusha)
                        issues.append(
                            SyntaxIssue(
                                token_index=first_verb_idx,
                                token_text=v_tok.text_deva,
                                issue_type="agreement_error",
                                title=title,
                                description=(
                                    f"Subject '{subj_tok.text_deva}' is {subj_purusha.name} puruSha, "
                                    f"{subj_vacana.name} vacana, but the verb '{v_tok.text_deva}' is "
                                    f"{actual.purusha.name} puruSha, {actual.vacana.name} vacana."
                                ),
                                suggested_text=sug_verb_deva,
                                rule_sutra=rule_sutra,
                            )
                        )
                elif not v_tok.verb_readings:
                    # Fallback for forms VerbGrammar does not index (lakaras
                    # other than लट्, or roots outside its coverage): the
                    # previous surface-heuristic checks, kept only as a net.
                    _legacy_agreement_fallback(issues, subj_tok, v_tok, first_verb_idx)

        return issues, compounds


def _agreement_title_and_rule(subj_purusha, is_person_mismatch: bool) -> tuple[str, str]:
    if subj_purusha == Purusha.Uttama:
        return ("Subject-Verb Agreement Error (उत्तमपुरुष-अन्वय-दोषः)", "अस्मद्युत्तमः (१.४.१०७)")
    if subj_purusha == Purusha.Madhyama:
        return ("Subject-Verb Agreement Error (मध्यमपुरुष-अन्वय-दोषः)",
                "युष्मद्युपपदे समानाधिकरणे स्थानिन्यपि मध्यमः (१.४.१०५)")
    return ("Subject-Verb Agreement Error (कर्तृ-क्रिया-अन्वय-दोषः)",
            "कर्तृ-क्रिया-वचनान्वय-नियमः (शेषे प्रथमः १.४.१०८ / तिङस्त्रीणि त्रीणि प्रथममध्यमोत्तमाः १.४.१०१)")


def _legacy_agreement_fallback(issues: list, subj_tok, v_tok, first_verb_idx: int) -> None:
    """Surface-heuristic agreement check, used only when neither the subject
    nor the verb carries a structured vidyut reading to check against."""
    s_slp1 = subj_tok.text_slp1
    s_ana = subj_tok.analysis or ""
    v_slp1 = v_tok.text_slp1
    v_ana = v_tok.analysis or ""

    pronoun_hit = _pronoun_lookup(PRONOUN_MAP, s_slp1)
    if pronoun_hit is not None:
        exp_purusha, exp_vacana = pronoun_hit
        if exp_purusha == "Uttama" and not ("Uttama" in v_ana or "उत्तम" in v_ana or v_slp1.endswith("Ami") or v_slp1.endswith("AvaH") or v_slp1.endswith("AmaH")):
            surf_stem = v_slp1[:-2] if v_slp1.endswith("ti") else v_slp1
            if surf_stem.endswith("a"):
                surf_stem = surf_stem[:-1]
            sug_verb_slp1 = surf_stem + ("Ami" if exp_vacana == "Eka" else "AvaH" if exp_vacana == "Dvi" else "AmaH")
            issues.append(SyntaxIssue(
                token_index=first_verb_idx, token_text=v_tok.text_deva, issue_type="agreement_error",
                title="Subject-Verb Agreement Error (उत्तमपुरुष-अन्वय-दोषः)",
                description=f"1st person subject '{subj_tok.text_deva}' (अस्मद्) requires Uttama Puruṣa verb (उत्तम पुरुष).",
                suggested_text=transliterate(sug_verb_slp1, Scheme.Slp1, Scheme.Devanagari),
                rule_sutra="अस्मद्युत्तमः (१.४.१०७)",
            ))
        elif exp_purusha == "Madhyama" and not ("Madhyama" in v_ana or "मध्यम" in v_ana or v_slp1.endswith("si") or v_slp1.endswith("TaH") or v_slp1.endswith("Ta")):
            surf_stem = v_slp1[:-2] if v_slp1.endswith("ti") else v_slp1
            sug_verb_slp1 = surf_stem + ("si" if exp_vacana == "Eka" else "TaH" if exp_vacana == "Dvi" else "Ta")
            issues.append(SyntaxIssue(
                token_index=first_verb_idx, token_text=v_tok.text_deva, issue_type="agreement_error",
                title="Subject-Verb Agreement Error (मध्यमपुरुष-अन्वय-दोषः)",
                description=f"2nd person subject '{subj_tok.text_deva}' (युष्मद्) requires Madhyama Puruṣa verb (मध्यम पुरुष).",
                suggested_text=transliterate(sug_verb_slp1, Scheme.Slp1, Scheme.Devanagari),
                rule_sutra="युष्मद्युपपदे समानाधिकरणे स्थानिन्यपि मध्यमः (१.४.१०५)",
            ))

    is_plural_subj = (
        "Bahu" in s_ana or "बहुवचन" in s_ana or s_slp1.endswith("AH")
        or s_slp1 in ["te", "tAH", "tAni", "ete", "vayam", "yUyam"]
    )
    if is_plural_subj and v_slp1.endswith("ti") and not v_slp1.endswith("nti"):
        sug_verb_slp1 = v_slp1[:-2] + "nti"
        issues.append(SyntaxIssue(
            token_index=first_verb_idx, token_text=v_tok.text_deva, issue_type="agreement_error",
            title="Number Agreement Error (वचन-अन्वय-दोषः)",
            description=f"Plural subject '{subj_tok.text_deva}' (बहुवचन) requires Bahuvacana verb.",
            suggested_text=transliterate(sug_verb_slp1, Scheme.Slp1, Scheme.Devanagari),
            rule_sutra="कर्तृ-क्रिया-वचनान्वय-नियमः (शेषे प्रथमः १.४.१०८ / तिङस्त्रीणि त्रीणि प्रथममध्यमोत्तमाः १.४.१०१)",
        ))
