"""
Grammar-driven verb-form recognition and correction.

Replaces fixed "wrong -> right" lookup tables with genuine Paninian
derivation: every root in the traditional Dhatupatha (2200+ roots, loaded
from vidyut's own data files, not curated here) has its लट्-कर्तरि
(present tense, kartari prayoga) paradigm derived once via
`vidyut.prakriya.Vyakarana`, and the results are indexed by surface form.

Checking whether a verb form is valid, what person/number it actually
carries, and what the correct form for a *different* person/number would
be, are therefore all answered by consulting an actual derivation and its
rule trace -- never by a hand-curated answer key.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from vidyut.prakriya import Data, Lakara, Prayoga, Pada, Purusha, Vacana, Vyakarana

PURUSHA_VACANA: list[tuple] = [
    (Purusha.Prathama, Vacana.Eka),
    (Purusha.Prathama, Vacana.Dvi),
    (Purusha.Prathama, Vacana.Bahu),
    (Purusha.Madhyama, Vacana.Eka),
    (Purusha.Madhyama, Vacana.Dvi),
    (Purusha.Madhyama, Vacana.Bahu),
    (Purusha.Uttama, Vacana.Eka),
    (Purusha.Uttama, Vacana.Dvi),
    (Purusha.Uttama, Vacana.Bahu),
]


@dataclass(frozen=True)
class VerbForm:
    dhatu_code: str      # Dhatupatha code, e.g. "01.1137"
    aupadeshika: str     # root as listed in the Dhatupatha (accents included), SLP1
    artha: str           # traditional meaning-gloss (SLP1), e.g. "gatO"
    purusha: Purusha
    vacana: Vacana


class VerbGrammar:
    """Derives and indexes the लट्-कर्तरि paradigm of every root in the Dhatupatha."""

    def __init__(self, prakriya_data_dir: str | Path):
        self._vyakarana = Vyakarana()
        data = Data(str(prakriya_data_dir))
        self._entries = {e.code: e for e in data.load_dhatu_entries()}
        self._by_surface: dict[str, list[VerbForm]] = {}
        self._build_index()

    def _build_index(self) -> None:
        for code, entry in self._entries.items():
            for purusha, vacana in PURUSHA_VACANA:
                for text in self._derive(entry.dhatu, purusha, vacana):
                    self._by_surface.setdefault(text, []).append(
                        VerbForm(code, entry.dhatu.aupadeshika, entry.artha, purusha, vacana)
                    )

    def _derive(self, dhatu, purusha: Purusha, vacana: Vacana) -> set[str]:
        try:
            tin = Pada.Tinanta(dhatu, Prayoga.Kartari, Lakara.Lat, purusha, vacana)
            return {r.text for r in self._vyakarana.derive(tin)}
        except Exception:
            return set()

    def lookup(self, surface_slp1: str) -> list[VerbForm]:
        """All (root, puruSha, vacana) readings for an exact लट्-कर्तरि surface form."""
        return self._by_surface.get(surface_slp1, [])

    def suggest(self, dhatu_code: str, purusha: Purusha, vacana: Vacana) -> set[str]:
        """Derive the correct लट्-कर्तरि form of `dhatu_code` for the given puruSha/vacana."""
        entry = self._entries.get(dhatu_code)
        if entry is None:
            return set()
        return self._derive(entry.dhatu, purusha, vacana)

    def root_matches(self, dhatu_code: str, hint_slp1: str) -> bool:
        """True if a plain-text root hint (e.g. 'gam', 'dA') plausibly names this dhatu.

        Dhatupatha entries carry accent/it-marker notation (e.g. 'ga\\mx~' for
        गम्), so a hint is matched by containment against the raw aupadeshika
        rather than requiring an exact clean-root reconstruction.
        """
        entry = self._entries.get(dhatu_code)
        if entry is None:
            return False
        return hint_slp1 in entry.dhatu.aupadeshika
