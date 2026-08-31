"""
Supplemental Sanskrit Lexicon & Morphological Expander.

Provides:
  1. Paninian subanta/tinanta expansion using vidyut.prakriya for common nominal
     stems, textbook terms, proper nouns, and feminine prātipadikas (e.g. bAlikA,
     adhyApikA, SiSya, etc.) not included in vidyut's base kosha data.
  2. Built-in index of Sanskrit avyayas (indeclinables).
  3. Extensible dictionary for custom textbook / domain words.
"""

from dataclasses import dataclass
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
class LexiconEntry:
    text_slp1: str
    lemma: str
    analysis: str
    is_valid: bool = True


# Standard avyayas (indeclinables) commonly used in Sanskrit texts
COMMON_AVYAYAS: dict[str, str] = {
    "ca": "Avyaya (and / समुच्चय)",
    "eva": "Avyaya (indeed / only / निश्चय)",
    "iti": "Avyaya (thus / quote marker)",
    "tu": "Avyaya (but / indeed)",
    "api": "Avyaya (also / even)",
    "yathA": "Avyaya (just as)",
    "tathA": "Avyaya (so / likewise)",
    "yadA": "Avyaya (when)",
    "tadA": "Avyaya (then)",
    "kadA": "Avyaya (when? / interrogative)",
    "katham": "Avyaya (how)",
    "kutra": "Avyaya (where)",
    "atra": "Avyaya (here)",
    "tatra": "Avyaya (there)",
    "yatra": "Avyaya (where / relative)",
    "sarvatra": "Avyaya (everywhere)",
    "adya": "Avyaya (today)",
    "Svas": "Avyaya (tomorrow)",
    "hyas": "Avyaya (yesterday)",
    "punar": "Avyaya (again)",
    "punaH": "Avyaya (again)",
    "sadA": "Avyaya (always)",
    "sarvadA": "Avyaya (always)",
    "vina": "Avyaya (without)",
    "vinA": "Avyaya (without)",
    "saha": "Avyaya (with / together)",
    "alam": "Avyaya (enough / competent)",
    "na": "Avyaya (negation / not)",
    "mA": "Avyaya (prohibition / do not)",
    "aho": "Avyaya (interjection / wonder)",
    "he": "Avyaya (vocative address)",
    "bhoH": "Avyaya (vocative address)",
    "nizcaya": "Avyaya (certainly)",
    "namaH": "Avyaya (salutations)",
    "namas": "Avyaya (salutations)",
    "svasti": "Avyaya (well-being)",
}


class SupplementalLexicon:
    """In-memory supplemental lexicon backed by Paninian paradigm generator."""

    def __init__(self):
        self._entries: dict[str, LexiconEntry] = {}
        self._vyakarana = Vyakarana()
        self._load_avyayas()
        self._generate_common_paradigms()

    def _load_avyayas(self):
        for slp1, analysis in COMMON_AVYAYAS.items():
            self._entries[slp1] = LexiconEntry(
                text_slp1=slp1,
                lemma=slp1,
                analysis=analysis,
            )

    def _generate_common_paradigms(self):
        """Pre-generates subanta paradigm declensions for everyday textbook stems."""
        stems_to_generate = [
            # Feminine stems (nyāp - ā ending)
            (Pratipadika.nyap("bAlikA"), Linga.Stri, "bAlikA"),
            (Pratipadika.nyap("adhyApikA"), Linga.Stri, "adhyApikA"),
            (Pratipadika.nyap("CAtrA"), Linga.Stri, "CAtrA"),
            (Pratipadika.nyap("mahilA"), Linga.Stri, "mahilA"),
            (Pratipadika.nyap("kanyA"), Linga.Stri, "kanyA"),
            (Pratipadika.nyap("latA"), Linga.Stri, "latA"),
            (Pratipadika.nyap("vARI"), Linga.Stri, "vARI"),
            (Pratipadika.nyap("nArI"), Linga.Stri, "nArI"),
            (Pratipadika.nyap("sevA"), Linga.Stri, "sevA"),
            (Pratipadika.nyap("pUjA"), Linga.Stri, "pUjA"),
            (Pratipadika.nyap("vidyA"), Linga.Stri, "vidyA"),
            (Pratipadika.nyap("Bakti"), Linga.Stri, "Bakti"),
            (Pratipadika.nyap("SAnti"), Linga.Stri, "SAnti"),
            (Pratipadika.nyap("mAtf"), Linga.Stri, "mAtf"),
            # Masculine stems
            (Pratipadika.basic("bAlaka"), Linga.Pum, "bAlaka"),
            (Pratipadika.basic("CAtra"), Linga.Pum, "CAtra"),
            (Pratipadika.basic("adhyApaka"), Linga.Pum, "adhyApaka"),
            (Pratipadika.basic("SiSya"), Linga.Pum, "SiSya"),
            (Pratipadika.basic("guru"), Linga.Pum, "guru"),
            (Pratipadika.basic("pitf"), Linga.Pum, "pitf"),
            (Pratipadika.basic("svAmin"), Linga.Pum, "svAmin"),
            (Pratipadika.basic("satsaNga"), Linga.Pum, "satsaNga"),
            (Pratipadika.basic("vizArada"), Linga.Pum, "vizArada"),
            # Neuter stems
            (Pratipadika.basic("pustaka"), Linga.Napumsaka, "pustaka"),
            (Pratipadika.basic("mitra"), Linga.Napumsaka, "mitra"),
            (Pratipadika.basic("Pala"), Linga.Napumsaka, "Pala"),
            (Pratipadika.basic("vanam"), Linga.Napumsaka, "vana"),
            (Pratipadika.basic("jalam"), Linga.Napumsaka, "jala"),
        ]

        vibhaktis = [
            (Vibhakti.Prathama, "Prathama"),
            (Vibhakti.Dvitiya, "Dvitiya"),
            (Vibhakti.Trtiya, "Trtiya"),
            (Vibhakti.Caturthi, "Caturthi"),
            (Vibhakti.Panchami, "Panchami"),
            (Vibhakti.Sasthi, "Sasthi"),
            (Vibhakti.Saptami, "Saptami"),
            (Vibhakti.Sambodhana, "Sambodhana"),
        ]

        vacanas = [
            (Vacana.Eka, "Eka"),
            (Vacana.Dvi, "Dvi"),
            (Vacana.Bahu, "Bahu"),
        ]

        for p_obj, linga, lemma in stems_to_generate:
            for vib_val, vib_name in vibhaktis:
                for vac_val, vac_name in vacanas:
                    try:
                        p = Pada.Subanta(
                            pratipadika=p_obj,
                            linga=linga,
                            vibhakti=vib_val,
                            vacana=vac_val,
                        )
                        for r in self._vyakarana.derive(p):
                            form_slp1 = r.text
                            analysis = (
                                f"Subanta (linga={linga.name}, "
                                f"vibhakti={vib_name}, vacana={vac_name})"
                            )
                            # Store both surface form and s/r-normalized padanta form
                            self._entries[form_slp1] = LexiconEntry(
                                text_slp1=form_slp1,
                                lemma=lemma,
                                analysis=analysis,
                            )
                            # If ends in 'H' (visarga), also store with 's' and 'r' for kosha compatibility
                            if form_slp1.endswith("H"):
                                s_form = form_slp1[:-1] + "s"
                                self._entries[s_form] = LexiconEntry(
                                    text_slp1=s_form,
                                    lemma=lemma,
                                    analysis=analysis,
                                )
                    except Exception:
                        continue

    def lookup(self, slp1_word: str) -> Optional[LexiconEntry]:
        """Look up a word in the supplemental lexicon."""
        # 1. Exact match
        if slp1_word in self._entries:
            return self._entries[slp1_word]

        # 2. Visarga <-> s / r transformation
        if slp1_word.endswith("H"):
            s_form = slp1_word[:-1] + "s"
            if s_form in self._entries:
                return self._entries[s_form]
        elif slp1_word.endswith("s") or slp1_word.endswith("r"):
            h_form = slp1_word[:-1] + "H"
            if h_form in self._entries:
                return self._entries[h_form]

        # 3. Anusvara <-> m transformation
        if slp1_word.endswith("M"):
            m_form = slp1_word[:-1] + "m"
            if m_form in self._entries:
                return self._entries[m_form]
        elif slp1_word.endswith("m"):
            m_form = slp1_word[:-1] + "M"
            if m_form in self._entries:
                return self._entries[m_form]

        return None
