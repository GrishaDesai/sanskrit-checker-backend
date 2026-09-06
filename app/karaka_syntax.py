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


# कृत् suffixes that form an indeclinable rather than a declinable stem.
AVYAYA_KRT = frozenset({"ktvA", "lyap", "tumun", "tosun", "kasun"})


def _strip_it_markers(krt_name: str) -> str:
    """Drop the anubandha notation from a कृत् name ('tumu~n' -> 'tumun')."""
    return krt_name.replace("~", "").replace("\\", "")


def _starts_new_clause(tok) -> bool:
    """True if this token opens a new clause, so nothing before it is in
    apposition with it. इति closes the quoted/embedded clause it follows and
    is routinely written fused to the next word (इत्यर्थः, इत्येवम्), so the
    marker is matched at the start of the surface rather than only as a
    standalone token."""
    return tok.text_slp1.startswith(("iti", "ity"))


def _is_avyaya_token(tok) -> bool:
    """True if any of this token's readings is an अव्यय (indeclinable).

    An avyaya has no vibhakti at all, so it can never be a कर्ता -- but
    vidyut's Kosha carries unrelated declinable homographs under the same
    surface key, and a spurious Prathama reading of हि or तथा was enough to
    make the subject-finder announce "Subject 'हि'". The `is_avyaya` flag on
    the Kosha prātipadika is vidyut's own answer to this question, the same
    source `SanskritEngine._is_function_word` reads.

    Any avyaya reading disqualifies the token rather than only a best-ranked
    one: a word that *can* be read as a particle is not solid enough ground
    to assert a कर्तृ-क्रिया agreement error against.
    """
    if (getattr(tok, "analysis", None) or "").startswith("Avyaya"):
        return True
    for entry in getattr(tok, "nominal_entries", []):
        pratipadika_entry = getattr(entry, "pratipadika_entry", None)
        pratipadika = getattr(pratipadika_entry, "pratipadika", None)
        if getattr(pratipadika, "is_avyaya", False):
            return True
        # अव्ययकृत्: a कृदन्त formed with क्त्वा, ल्यप् or तुमुन् is
        # indeclinable (क्त्वातोसुन्कसुनः १.१.४० and कृन्मेजन्तः १.१.३९), so
        # it has no liṅga to agree in -- वारयित्वा is a gerund, not a
        # masculine nominative, however the Kosha's Subanta wrapper presents
        # it. The krt suffix is read from vidyut's own Krdanta entry.
        krt = getattr(pratipadika_entry, "krt", None)
        if krt is not None and _strip_it_markers(str(krt)) in AVYAYA_KRT:
            return True
    return False


@dataclass
class SyntaxIssue:
    token_index: int
    token_text: str
    issue_type: str        # "karaka_error" | "agreement_error" | "upapada_error"
    title: str
    description: str
    suggested_text: Optional[str] = None
    rule_sutra: Optional[str] = None
    # Mirrors TokenResult.severity. A syntax finding is only a confirmed
    # defect when the morphology it rests on is unambiguous; where the
    # analysis itself offers several readings, the finding is offered for
    # human judgement instead of asserted.
    severity: str = "error"


@dataclass
class SamasaAnalysis:
    compound_text: str
    compound_type: str
    vigraha_vakya: str
    components: list[str]


# Coordinating particles. च and वा are postpositive in Sanskrit -- "A B च"
# and "A च B च" both mean "A and B" -- so a coordinator may follow the
# conjuncts rather than stand between them, and both shapes must be matched.
COORDINATING_PARTICLES = frozenset({"ca", "vA", "aTavA", "kiYca"})

# Cases that cannot themselves mark a kāraka role, so a nominal in one of
# them cannot be an adjunct competing with the verb's governed argument.
# शेषे षष्ठी (२.३.५०) defines षष्ठी as exactly the relation left over once
# every kāraka is assigned -- which is what makes a genitive in an argument
# slot a confirmable error, where an instrumental or locative would just be
# some other kāraka.
NON_KARAKA_VIBHAKTIS = frozenset({Vibhakti.Sasthi})

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

    def _prathama_ambiguity(self, tok) -> tuple[bool, bool]:
        """(linga_is_ambiguous, vacana_is_ambiguous) for a token's Prathama reading.

        Reported per grammatical category, because each check may only be
        blocked by ambiguity in the categories it actually relies on. Verb
        agreement turns on vacana alone, so बालकाः -- whose top-rank Prathama
        readings are split Pum/Stri but agree on Bahu -- is perfectly solid
        ground for a कर्तृ-क्रिया error and must stay at error tier. The liṅga
        check is blocked by exactly the ambiguity the verb check ignores.

        "Ambiguous" means the morphological analysis *itself* offers more than
        one answer at its own top rank: several liṅgas, or several vacanas,
        among the best-ranked (Basic-preferred, see `_rank_nominal_entries`)
        Prathama readings. Ranking matters here -- counting raw Kosha entries
        instead would call वृक्षः ambiguous (30 readings) and lose a genuine
        gold-set gender error, whereas at top rank वृक्षः is unambiguously
        Pum/Eka and या really is Pum-or-Stri.

        A liṅga clash read off an analysis that was not sure of the liṅga in
        the first place is not a confirmed defect, so callers demote it to
        review rather than dropping it.
        """
        prathama = [e for e in getattr(tok, "nominal_entries", [])
                    if e.vibhakti == Vibhakti.Prathama]
        if not prathama:
            return False, False
        ranked = self._rank_nominal_entries(prathama)
        best_kind = type(ranked[0].pratipadika_entry).__name__.endswith("Basic")
        top = [e for e in prathama
               if type(e.pratipadika_entry).__name__.endswith("Basic") == best_kind]
        return (len({e.linga.name for e in top}) > 1,
                len({e.vacana.name for e in top}) > 1)

    def _vacana_is_undetermined(self, tok) -> bool:
        """True if the analysis does not settle the token's number.

        Verb agreement turns on vacana alone, so what matters is not which
        case won but whether every reading agrees on the number. The -ए ending
        of an a-stem is Saptamī *singular* and Prathamā/Dvitīyā *dual* at once,
        so स्थिते, युद्धे, निरोधे and सर्वात्मके carry both Eka and Dvi
        readings and cannot support a confirmed number mismatch -- these were
        locatives being read as nominative duals. The Prathamā/Dvitīyā
        syncretism that बालकाः and बालकौ show is harmless by the same measure:
        both readings give the same vacana, so the number is settled and the
        कर्तृ-क्रिया error stands.
        """
        entries = list(getattr(tok, "nominal_entries", []))
        if not entries:
            return False
        # A dropped visarga changes the number, not just the spelling. This
        # corpus (and Sanskrit print generally) writes -ā for -āḥ, so नरा
        # stands for नराः and प्रतिलोमा for प्रतिलोमाः: the Kosha reads the
        # bare form as Prathamā *singular* feminine while the sentence means
        # plural. The engine already treats visarga as a padānta variant when
        # *recognising* a word (PADANTA_FINAL_VARIANTS); the same variation
        # has to count when judging number, or the singular reading is taken
        # as settled and the verb reported as wrongly plural.
        restored = getattr(tok, "_visarga_restored_entries", None)
        if restored is None:
            restored = self._visarga_restored_entries(tok)
        entries += restored
        ranked = self._rank_nominal_entries(entries)
        best_is_basic = type(ranked[0].pratipadika_entry).__name__.endswith("Basic")
        top = [e for e in entries
               if type(e.pratipadika_entry).__name__.endswith("Basic") == best_is_basic]
        return len({e.vacana.name for e in top}) > 1

    def _visarga_restored_entries(self, tok) -> list:
        """Readings the token would have if a dropped visarga were restored.

        Only for a token written with a bare final long -ā, which is where the
        -āḥ / -ā ambiguity actually arises; a lookup helper is supplied by the
        engine so this stays a Kosha question, not a string one.
        """
        lookup = getattr(tok, "kosha_lookup", None)
        if lookup is None or not tok.text_slp1.endswith("A"):
            return []
        return [e for e in lookup(tok.text_slp1 + "H")
                if type(e).__name__.endswith("Subanta")]

    def _has_coordinated_subject(self, tokens, verb_idx: int) -> bool:
        """True if the words before this verb look like a coordinated (द्वन्द्व)
        subject, whose number is the *combined* count of its conjuncts.

        Two singular subjects joined by च act as a dual: तस्य पुत्रः कन्या च
        वर्तेते is correct Sanskrit, and the singular वर्तते that a
        conjunct-by-conjunct reading demands would corrupt it. The
        subject-verb check reads one nominal's vacana and cannot see that it
        is one of several, so it is suppressed here rather than allowed to
        assert.

        This is a purely local pattern -- is there a coordinating particle
        among the nominals preceding this verb -- not a structural judgement
        about which nominal binds to what. It deliberately requires *two or
        more* prathamā-capable nominals as well as the particle, so an
        unrelated च elsewhere in a single-subject sentence does not silence a
        genuine agreement error.
        """
        nominals = 0
        coordinator = False
        for idx in range(verb_idx):
            tok = tokens[idx]
            if tok.text_slp1 in COORDINATING_PARTICLES:
                coordinator = True
                continue
            if _is_avyaya_token(tok):
                continue
            if _pronoun_lookup(PRONOUN_MAP, tok.text_slp1) is not None:
                continue
            if any(e.vibhakti == Vibhakti.Prathama for e in self._top_rank_entries(tok)):
                nominals += 1
        return coordinator and nominals >= 2

    def _top_rank_entries(self, tok) -> list:
        """A token's nominal readings at its own best rank (Basic-preferred).

        Lower-ranked कृदन्त homographs are noise for every question asked of
        them here, and vidyut does not order entries by frequency, so each
        check that inspects a token's grammar looks at this set rather than at
        every entry or at an arbitrary first one.
        """
        entries = getattr(tok, "nominal_entries", [])
        if not entries:
            return []
        ranked = self._rank_nominal_entries(entries)
        best_is_basic = type(ranked[0].pratipadika_entry).__name__.endswith("Basic")
        return [e for e in entries
                if type(e.pratipadika_entry).__name__.endswith("Basic") == best_is_basic]

    def _sole_argument_candidate(self, tokens, verb_idx: int, verb_indices: list):
        """The one nominal that can be this verb's governed argument, or None.

        Returns None -- asserting nothing -- unless the sentence is narrow
        enough for the answer to be certain without a dependency parse:

        * **one finite verb only.** With two verbs there are two clauses and
          nothing here can say which one a given nominal belongs to.
        * **every pre-verb word analysed.** An unrecognised token could itself
          be the argument, so its presence makes the field unknown.
        * **exactly one non-Prathamā nominal.** The Prathamā one is the कर्ता;
          if exactly one other nominal remains, it is the argument by
          elimination. With two or more, choosing between them is precisely
          the binding problem a parser is needed for, and guessing is how the
          old check produced its false positives.

        Cross-clause binding and multi-nominal disambiguation are out of scope
        for this phase by construction, not by omission.
        """
        if len(verb_indices) != 1:
            return None
        candidate = None
        for n_idx in range(verb_idx):
            tok = tokens[n_idx]
            if _is_avyaya_token(tok):
                continue
            if _pronoun_lookup(PRONOUN_MAP, tok.text_slp1) is not None:
                continue
            top = self._top_rank_entries(tok)
            if not top:
                return None
            vibhaktis = {e.vibhakti for e in top}
            if vibhaktis <= {Vibhakti.Prathama, Vibhakti.Sambodhana}:
                continue          # the subject / a vocative
            if candidate is not None:
                return None       # more than one candidate: needs a parser
            candidate = (n_idx, tok, vibhaktis)
        return candidate

    def _prathama_vacana(self, tok):
        """The vacana of a token's best-ranked *Prathama* reading, or None."""
        prathama = [e for e in getattr(tok, "nominal_entries", [])
                    if e.vibhakti == Vibhakti.Prathama]
        if not prathama:
            return None
        return self._rank_nominal_entries(prathama)[0].vacana

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
        # अस्मद्युत्तमः (१.४.१०७) makes उत्तम पुरुष conditional on अस्मद् being
        # the कर्ता, and युष्मद्युपपदे ... मध्यमः (१.४.१०५) makes मध्यम
        # conditional on युष्मद्. With neither pronoun in the sentence, a
        # first- or second-person reading of a word that is also an ordinary
        # nominal is ruled out by those sūtras -- which is what भावः needs:
        # भावः is a genuine उत्तम-द्विवचन of भा (02.0046) as well as the common
        # noun, and the तिङन्त reading was winning and producing "the verb
        # 'भावः' is Uttama puruSha".
        has_uttama_madhyama_pronoun = any(
            (_pronoun_lookup(PRONOUN_MAP, t.text_slp1) or ("Prathama",))[0]
            in ("Uttama", "Madhyama")
            for t in tokens
        )

        verb_indices = []
        for i, t in enumerate(tokens):
            analysis_str = t.analysis or ""
            t_slp1 = t.text_slp1
            if (
                t.verb_readings
                and not has_uttama_madhyama_pronoun
                and all(vf.purusha != Purusha.Prathama for vf in t.verb_readings)
                and any(type(e.pratipadika_entry).__name__.endswith("Basic")
                        and e.vibhakti == Vibhakti.Prathama
                        for e in self._top_rank_entries(t))
            ):
                continue
            if (
                t.verb_readings
                or "Tinanta" in analysis_str
                or "तिङन्त" in analysis_str
                or "Lakara" in analysis_str
                or t_slp1 in ["paWati", "gacCati", "pibati", "rakzati", "KAdati", "paSyati", "paWanti", "gacCanti", "pibanti", "rakzanti", "paWasi", "gacCasi", "paWAmi", "gacCAmi"]
            ):
                verb_indices.append(i)

        # 3. Kāraka & Verb-Argument Government Checking
        #
        # Deliberately narrow, per the conditions below. Previously each of
        # these checks asked only "is this argument in Ṣaṣṭhī?", so a wrong
        # case that was not genitive -- an object in Tṛtīyā, say -- was never
        # tested at all. The test is now "is the argument in the case this
        # root governs?", which covers every wrong case with one mechanism
        # while the gating keeps it from firing on real prose.
        for v_idx in verb_indices:
            v_tok = tokens[v_idx]
            v_slp1 = v_tok.text_slp1

            # Determine root/dhatu: prefer the root vidyut's own derivation
            # engine identified for this exact surface form over prefix
            # matching, which is wrong for any verb class with reduplication
            # or a guna/vrddhi-altered stem (e.g. ददाति from दा does not
            # start with "dA").
            requirements = []
            dhatu_clean = self._identify_dhatu_hint(v_tok.verb_readings, TRANSITIVE_DHATU_MAP, v_slp1)
            if dhatu_clean is None and "rakz" in v_slp1 and "rakz" in TRANSITIVE_DHATU_MAP:
                dhatu_clean = "rakz"
            if dhatu_clean and dhatu_clean in TRANSITIVE_DHATU_MAP:
                requirements.append((
                    Vibhakti.Dvitiya,
                    "Kāraka / Case Government Error (कर्मकारक-विभक्ति-दोषः)",
                    f"धातु '{TRANSITIVE_DHATU_MAP[dhatu_clean]}' is transitive (सकर्मक) and "
                    f"requires its direct object in Dvitiyā vibhakti (कर्मणि द्वितीया).",
                    "कर्मणि द्वितीया (२.३.२) / कर्तुरीप्सिततमं कर्म (१.४.४९)",
                ))

            caturthi_hint = self._identify_dhatu_hint(v_tok.verb_readings, CATURTHI_DHATU_MAP, v_slp1)
            if caturthi_hint:
                sutra, desc = CATURTHI_DHATU_MAP[caturthi_hint]
                requirements.append((
                    Vibhakti.Caturthi,
                    "Sampradāna Kāraka Error (सम्प्रदान-कारक-दोषः)", desc, sutra,
                ))

            panchami_hint = self._identify_dhatu_hint(v_tok.verb_readings, PANCHAMI_DHATU_MAP, v_slp1)
            if panchami_hint is None and "biBe" in v_slp1 and "BI" in PANCHAMI_DHATU_MAP:
                panchami_hint = "BI"
            if panchami_hint:
                sutra, desc = PANCHAMI_DHATU_MAP[panchami_hint]
                requirements.append((
                    Vibhakti.Panchami,
                    "Apādāna Kāraka Error (अपादान-कारक-दोषः)", desc, sutra,
                ))

            if not requirements:
                continue

            candidate = self._sole_argument_candidate(tokens, v_idx, verb_indices)
            if candidate is None:
                continue
            n_idx, n_tok, n_vibhaktis = candidate

            for required, title, desc, sutra in requirements:
                if required in n_vibhaktis:
                    continue   # a reading in the governed case exists; nothing to assert
                # A wrong case is only *confirmable* when the case actually
                # written cannot be a kāraka role of its own. Tṛtīyā can be
                # करण, Saptamī अधिकरण, Pañcamī अपादान -- all of which coexist
                # happily with the कर्म, so "बालकः कक्षायां पठति" has a
                # perfectly ordinary locative adjunct, not a miscased object.
                # Deciding whether such a nominal fills the कर्म slot or an
                # adjunct one is binding information morphology does not
                # carry. षष्ठी is the exception: शेषे षष्ठी (२.३.५०) defines it
                # as precisely the non-kāraka remainder, so a genitive
                # standing as a verb's only argument is a real defect.
                if not (n_vibhaktis <= NON_KARAKA_VIBHAKTIS):
                    continue
                suggested_slp1 = self._case_form(n_tok.nominal_entries, required)
                if suggested_slp1 is None:
                    continue   # no grammatically verified correction available
                found = "/".join(sorted(v.name for v in n_vibhaktis))
                issues.append(
                    SyntaxIssue(
                        token_index=n_idx,
                        token_text=n_tok.text_deva,
                        issue_type="karaka_error",
                        title=title,
                        description=f"{desc} '{n_tok.text_deva}' is in {found} vibhakti.",
                        suggested_text=transliterate(suggested_slp1, Scheme.Slp1, Scheme.Devanagari),
                        rule_sutra=sutra,
                    )
                )

        # 4. Upapada Vibhakti Checking (e.g. devasya namaH -> devAya namaH)
        #
        # This is where the case extension beyond षष्ठी is sound. An upapada
        # fixes the vibhakti of the word it governs outright -- नमः takes
        # चतुर्थी (२.३.२८), सह takes तृतीया (२.३.१९) -- and it governs the
        # word immediately beside it, not "some nominal in the clause". There
        # is no competing kāraka slot for an adjunct to occupy, so *any* case
        # other than the governed one is a confirmable error here, instead of
        # only षष्ठी as before. This covers instrumental and dative arguments.
        for i, t in enumerate(tokens):
            t_slp1 = t.text_slp1
            if t_slp1 not in UPAPADA_VIBHAKTI_MAP or i == 0:
                continue
            req_name, sutra, desc = UPAPADA_VIBHAKTI_MAP[t_slp1]
            allowed = {getattr(Vibhakti, part) for part in req_name.split("_")}
            prev_tok = tokens[i - 1]
            if _is_avyaya_token(prev_tok):
                continue
            prev_vibhaktis = {e.vibhakti for e in self._top_rank_entries(prev_tok)}
            if not prev_vibhaktis or prev_vibhaktis & allowed:
                continue   # unanalysed, or a reading in a governed case exists

            # Correct into the first governed case the word can actually be
            # derived in; where विना licenses several, any of them is right.
            suggested_slp1 = next(
                (f for f in (self._case_form(prev_tok.nominal_entries, v)
                             for v in sorted(allowed, key=lambda x: x.name))
                 if f is not None),
                None,
            )
            if suggested_slp1 is None:
                continue
            found = "/".join(sorted(v.name for v in prev_vibhaktis))
            issues.append(
                SyntaxIssue(
                    token_index=i - 1,
                    token_text=prev_tok.text_deva,
                    issue_type="upapada_error",
                    title="Upapada Vibhakti Error (उपपद-विभक्ति-दोषः)",
                    description=f"{desc}, but '{prev_tok.text_deva}' is in {found} vibhakti.",
                    suggested_text=transliterate(suggested_slp1, Scheme.Slp1, Scheme.Devanagari),
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
        # Coordinated nominals are list items, not विशेषण–विशेष्य, and list
        # members need not share liṅga: कक्षौ स्तनौ गलः पृष्ठं जघनम् ऊरू च
        # स्थानानि enumerates body parts across three genders and is correct.
        # The same local particle test used for the subject applies here.
        if not has_action_verb and not self._has_coordinated_subject(tokens, len(tokens)):
            copula_indices = set(verb_indices)
            for i in range(len(tokens) - 1):
                a = tokens[i]
                j = i + 1
                if j in copula_indices:   # skip over a copula between the two nominals
                    j += 1
                if j >= len(tokens) or j in copula_indices:
                    continue
                b = tokens[j]

                # An अव्यय has no liṅga to agree in. वा, केवलम् and the like
                # carry unrelated declinable homographs in the Kosha, which is
                # the whole reason "'वा' (Pum) does not agree with 'चूर्णं'"
                # was ever emitted.
                if _is_avyaya_token(a) or _is_avyaya_token(b):
                    continue

                # Never pair across a clause boundary. इति closes the clause it
                # follows, so ज्ञातव्यम् and इत्यर्थः are simply not in
                # apposition -- and इति frequently arrives fused to the next
                # word (इत्यर्थः), so the marker is looked for at the start of
                # the token, not only as a token of its own.
                if _starts_new_clause(b) or _starts_new_clause(a):
                    continue

                a_lingas = self._prathama_lingas(a)
                b_lingas = self._prathama_lingas(b)
                if not (a_lingas and b_lingas and not (a_lingas & b_lingas)):
                    continue

                # विशेषण and विशेष्य agree in liṅga, vacana *and* vibhakti
                # together (सरूपाणाम् ... they are समानाधिकरण). Both readings
                # are Prathama by construction here, so vacana is the part
                # still to check: मृदा/लिप्तं and भावा/व्याख्याताः differ in
                # number and were never in apposition to begin with.
                a_linga_amb, a_vacana_amb = self._prathama_ambiguity(a)
                b_linga_amb, b_vacana_amb = self._prathama_ambiguity(b)
                a_vacana = self._prathama_vacana(a)
                b_vacana = self._prathama_vacana(b)
                if a_vacana is not None and b_vacana is not None and a_vacana != b_vacana:
                    continue

                # Where the analysis itself was unsure of the liṅga, the clash
                # is offered, not asserted.
                severity = ("review"
                            if (a_linga_amb or b_linga_amb or a_vacana_amb or b_vacana_amb)
                            else "error")

                issues.append(
                    SyntaxIssue(
                        token_index=i,
                        token_text=a.text_deva,
                        issue_type="agreement_error",
                        title="Gender Agreement Error (लिङ्ग-अन्वय-दोषः)",
                        description=(
                            f"'{a.text_deva}' ({'/'.join(sorted(a_lingas))}) does not agree in "
                            f"liNga with '{b.text_deva}' ({'/'.join(sorted(b_lingas))})."
                            + ("  The morphological analysis reports more than one possible "
                               "reading for at least one of these words, so this is offered "
                               "for review rather than reported as a confirmed error."
                               if severity == "review" else "")
                        ),
                        suggested_text=None,
                        rule_sutra="विशेषणं विशेष्येण बहुलम् (विशेषण-विशेष्य-लिङ्ग-अन्वयः)",
                        severity=severity,
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
        if tokens and verb_indices and not self._has_coordinated_subject(tokens, verb_indices[0]):
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
                # An indeclinable has no vibhakti and cannot be the कर्ता.
                # Skipping it keeps looking rather than abandoning the search,
                # so a real subject sitting after a particle is still found.
                if _is_avyaya_token(t):
                    continue
                # A word whose number the analysis does not settle is not a
                # subject *candidate* at all -- it must not be selected and
                # then demoted. The -ए ending of an a-stem is Saptamī singular
                # and Prathamā dual at once, so ग्रामे in "ग्रामे गच्छति" is a
                # locative adjunct with an elided subject; picking it and
                # reporting "Subject 'ग्रामे' ... Dvi vacana" is wrong even at
                # review tier, because there is no subject-verb relation here
                # to have an opinion about. Skipping keeps the search going,
                # so a real subject later in the clause is still found.
                if self._vacana_is_undetermined(t):
                    continue
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
                    # The vacana must come from the *Prathama* reading. Taking
                    # the best-ranked reading over all cases picked up नरा's
                    # Tṛtīyā-singular homograph and then complained that
                    # पश्यन्ति was plural.
                    subj_vacana = self._prathama_vacana(subj_tok) or (
                        Vacana.Bahu if s_slp1.endswith("AH") or s_slp1 in ["te", "tAH", "tAni", "ete"] else Vacana.Eka
                    )

                agrees = any(
                    vf.purusha == subj_purusha and vf.vacana == subj_vacana
                    for vf in v_tok.verb_readings
                )

                # Same discipline as the liṅga check: assert only when the
                # subject's own analysis is unambiguous. A subject whose
                # Prathama reading is split across vacanas (नरा), or that has
                # no structured reading at all and was picked by the
                # surface-ending heuristic (महामोहावृतमनाः -- a -मनस् compound
                # whose singular ends -मनाः, which the "-AH means plural"
                # guess reads backwards), is not solid ground for a confirmed
                # कर्तृ-क्रिया error.
                subj_vacana_ambiguous = self._vacana_is_undetermined(subj_tok)
                if pronoun_hit is None and not subj_tok.nominal_entries:
                    subj_vacana_ambiguous = True
                agreement_severity = "review" if subj_vacana_ambiguous else "error"

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
                                severity=agreement_severity,
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
