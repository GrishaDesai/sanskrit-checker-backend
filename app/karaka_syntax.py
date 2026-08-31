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
    Pada,
)


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

    def __init__(self):
        self._vyakarana = Vyakarana()

    def _extract_nominal_stem(self, slp1_word: str) -> str:
        """Extracts base nominal stem from common inflected forms."""
        if slp1_word.endswith("AnAm") or slp1_word.endswith("ARAm"):
            return slp1_word[:-4]
        if slp1_word.endswith("asya"):
            return slp1_word[:-4]
        if slp1_word.endswith("At"):
            return slp1_word[:-2]
        if slp1_word.endswith("Aya"):
            return slp1_word[:-3]
        if slp1_word.endswith("ena") or slp1_word.endswith("eRa"):
            return slp1_word[:-3]
        if slp1_word.endswith("AH"):
            return slp1_word[:-2]
        if slp1_word.endswith("as"):
            return slp1_word[:-2]
        if slp1_word.endswith("aH"):
            return slp1_word[:-2]
        return slp1_word

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

        # 2. Extract verbs, nouns, pronouns, and upapadas
        verb_indices = []
        for i, t in enumerate(tokens):
            analysis_str = t.analysis or ""
            t_slp1 = t.text_slp1
            if (
                "Tinanta" in analysis_str
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

            # Determine root/dhatu
            dhatu_clean = None
            for d in TRANSITIVE_DHATU_MAP:
                if v_slp1.startswith(d) or d in v_analysis or (d == "rakz" and "rakz" in v_slp1):
                    dhatu_clean = d
                    break

            # Check Transitive Root requiring Dvitiyā (Karma Kāraka)
            if dhatu_clean and dhatu_clean in TRANSITIVE_DHATU_MAP:
                for n_idx in range(v_idx):
                    n_tok = tokens[n_idx]
                    n_analysis = n_tok.analysis or ""
                    n_slp1 = n_tok.text_slp1

                    if "Sasthi" in n_analysis or "षष्ठी" in n_analysis or n_slp1.endswith("AnAm") or n_slp1.endswith("ARAm") or n_slp1.endswith("asya"):
                        stem_slp1 = self._extract_nominal_stem(n_slp1)
                        is_plural = "Bahu" in n_analysis or "बहुवचन" in n_analysis or n_slp1.endswith("AnAm") or n_slp1.endswith("ARAm")
                        
                        dvitiya_slp1 = stem_slp1 + "An" if is_plural else stem_slp1 + "am"
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
            for d, (sutra, desc) in CATURTHI_DHATU_MAP.items():
                if v_slp1.startswith(d) or d in v_analysis:
                    for n_idx in range(v_idx):
                        n_tok = tokens[n_idx]
                        n_analysis = n_tok.analysis or ""
                        n_slp1 = n_tok.text_slp1
                        if "Sasthi" in n_analysis or "षष्ठी" in n_analysis or n_slp1.endswith("asya"):
                            stem_slp1 = self._extract_nominal_stem(n_slp1)
                            caturthi_slp1 = stem_slp1 + "Aya"
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
            for d, (sutra, desc) in PANCHAMI_DHATU_MAP.items():
                if v_slp1.startswith(d) or d in v_analysis or "biBe" in v_slp1:
                    for n_idx in range(v_idx):
                        n_tok = tokens[n_idx]
                        n_analysis = n_tok.analysis or ""
                        n_slp1 = n_tok.text_slp1
                        if "Sasthi" in n_analysis or "षष्ठी" in n_analysis or n_slp1.endswith("asya"):
                            stem_slp1 = self._extract_nominal_stem(n_slp1)
                            panchami_slp1 = stem_slp1 + "At"
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
                if req_vib == "Caturthi" and ("Sasthi" in prev_ana or "षष्ठी" in prev_ana or prev_slp1.endswith("asya")):
                    stem_slp1 = self._extract_nominal_stem(prev_slp1)
                    sug_slp1 = stem_slp1 + "Aya"
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

        # 5. Subject-Verb Agreement Checking (Puruṣa & Vacana Anvaya)
        if tokens and verb_indices:
            first_verb_idx = verb_indices[0]
            v_tok = tokens[first_verb_idx]
            v_ana = v_tok.analysis or ""
            v_slp1 = v_tok.text_slp1

            # Identify subject candidate among preceding tokens
            subj_tok = None
            for idx in range(first_verb_idx):
                t = tokens[idx]
                t_slp1 = t.text_slp1
                t_ana = t.analysis or ""
                if (
                    t_slp1 in PRONOUN_MAP
                    or "Prathama" in t_ana
                    or "प्रथमा" in t_ana
                    or t_slp1.endswith("AH")
                    or t_slp1.endswith("as")
                    or t_slp1.endswith("aH")
                    or t_slp1.endswith("o")
                    or t_slp1.endswith("An")
                ):
                    subj_tok = t
                    break

            if subj_tok:
                s_slp1 = subj_tok.text_slp1
                s_ana = subj_tok.analysis or ""

                # Pronoun checks
                if s_slp1 in PRONOUN_MAP:
                    exp_purusha, exp_vacana = PRONOUN_MAP[s_slp1]

                    if exp_purusha == "Uttama" and not ("Uttama" in v_ana or "उत्तम" in v_ana or v_slp1.endswith("Ami") or v_slp1.endswith("AvaH") or v_slp1.endswith("AmaH")):
                        # Build suggestion from surface verb: drop -ti -> -Ami / -AvaH / -AmaH
                        if v_slp1.endswith("ti"):
                            surf_stem = v_slp1[:-2]  # e.g. paWa, gacCa, piba, rakza
                        else:
                            surf_stem = v_slp1
                        # Trim trailing short 'a' before adding long-A suffix (paWa+Ami -> paWAmi)
                        if surf_stem.endswith("a"):
                            surf_stem = surf_stem[:-1]
                        sug_verb_slp1 = surf_stem + ("Ami" if exp_vacana == "Eka" else "AvaH" if exp_vacana == "Dvi" else "AmaH")
                        sug_verb_deva = transliterate(sug_verb_slp1, Scheme.Slp1, Scheme.Devanagari)

                        issues.append(
                            SyntaxIssue(
                                token_index=first_verb_idx,
                                token_text=v_tok.text_deva,
                                issue_type="agreement_error",
                                title="Subject-Verb Agreement Error (उत्तमपुरुष-अन्वय-दोषः)",
                                description=f"1st person subject '{subj_tok.text_deva}' (अस्मद्) requires Uttama Puruṣa verb (उत्तम पुरुष).",
                                suggested_text=sug_verb_deva,
                                rule_sutra="अस्मद्युत्तमः (१.४.१०७)",
                            )
                        )

                    elif exp_purusha == "Madhyama" and not ("Madhyama" in v_ana or "मध्यम" in v_ana or v_slp1.endswith("si") or v_slp1.endswith("TaH") or v_slp1.endswith("Ta")):
                        # Build suggestion from surface verb: drop -ti -> -si / -TaH / -Ta
                        if v_slp1.endswith("ti"):
                            surf_stem = v_slp1[:-2]
                        else:
                            surf_stem = v_slp1
                        sug_verb_slp1 = surf_stem + ("si" if exp_vacana == "Eka" else "TaH" if exp_vacana == "Dvi" else "Ta")
                        sug_verb_deva = transliterate(sug_verb_slp1, Scheme.Slp1, Scheme.Devanagari)

                        issues.append(
                            SyntaxIssue(
                                token_index=first_verb_idx,
                                token_text=v_tok.text_deva,
                                issue_type="agreement_error",
                                title="Subject-Verb Agreement Error (मध्यमपुरुष-अन्वय-दोषः)",
                                description=f"2nd person subject '{subj_tok.text_deva}' (युष्मद्) requires Madhyama Puruṣa verb (मध्यम पुरुष).",
                                suggested_text=sug_verb_deva,
                                rule_sutra="युष्मद्युपपदे समानाधिकरणे स्थानिन्यपि मध्यमः (१.४.१०५)",
                            )
                        )


                # Plural Subject + Singular Verb check (e.g. bAlakAH paWati -> paWanti)
                is_plural_subj = (
                    "Bahu" in s_ana
                    or "बहुवचन" in s_ana
                    or s_slp1.endswith("AH")
                    or s_slp1 in ["te", "tAH", "tAni", "ete", "vayam", "yUyam"]
                )
                if is_plural_subj and v_slp1.endswith("ti") and not v_slp1.endswith("nti"):
                    # Derive Bahuvacana by replacing final -ti with -nti on the surface verb form
                    # This preserves the correct vowel in the stem (e.g. paWa+ti -> paWa+nti not paW+nti)
                    sug_verb_slp1 = v_slp1[:-2] + "nti"  # drop 'ti', add 'nti'
                    sug_verb_deva = transliterate(sug_verb_slp1, Scheme.Slp1, Scheme.Devanagari)

                    issues.append(
                        SyntaxIssue(
                            token_index=first_verb_idx,
                            token_text=v_tok.text_deva,
                            issue_type="agreement_error",
                            title="Number Agreement Error (वचन-अन्वय-दोषः)",
                            description=f"Plural subject '{subj_tok.text_deva}' (बहुवचन) requires Bahuvacana verb '{sug_verb_deva}'.",
                            suggested_text=sug_verb_deva,
                            rule_sutra="कर्तृ-क्रिया-वचनान्वय-नियमः (शेषे प्रथमः १.४.१०८ / तिङस्त्रीणि त्रीणि प्रथममध्यमोत्तमाः १.४.१०१)",
                        )
                    )

        return issues, compounds
