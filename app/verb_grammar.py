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

# The (lakara, prayoga) paradigms this index derives and recognises.
#
# Deliberately not "every lakara": the full 11 x 2 space costs 14.3 s to build
# against a 1.2 s cold start, and 16 of those 22 combinations are worth about
# two tokens between them on the UFAL sample. Each entry below was measured
# individually for build cost against tokens recovered:
#
#   लङ्-कर्तरि    11 tokens / 0.53 s      लोट्-कर्तरि   6 tokens / 0.59 s
#   लट्-कर्मणि     5 tokens / 0.33 s      लृट्-कर्तरि   5 tokens / 0.49 s
#   लोट्-कर्मणि    5 tokens / 0.35 s
#
# लोट्-कर्तरि, लोट्-कर्मणि, लट्-कर्मणि and लृट्-कर्तरि were added, measured and
# then removed again. They cost 2.6 s of cold start and bought the *product*
# nothing measurable: the DCS unrecognised-token rate is 515/1617 (31.8%)
# with or without them, because the Kosha already carries these forms as
# Tinanta entries -- indexing them here changes which source recognises a
# word, not whether it is recognised. Their real beneficiary was the CoNLL-U
# bridge (+32 tokens), and the dependency parser that consumes it was measured
# and closed (see docs/vidyut-phase-scope.md §4.3). लङ् is kept because it is
# the cheapest of the set and past-tense forms are much the commonest in real
# prose, so the analysis label it fixes is the one users actually meet.
# लिट्-कर्तरि was never added: worst ratio measured, 5 tokens for 1.16 s.
#
# Recognition only: `karaka_syntax` admits just लट्-कर्तरि to its exact-match
# agreement path, so a form added here is tagged correctly but still routes to
# the legacy fallback for agreement.
INDEXED_PARADIGMS: list[tuple] = [
    (Lakara.Lat, Prayoga.Kartari),
    (Lakara.Lan, Prayoga.Kartari),
]


@dataclass(frozen=True)
class VerbForm:
    dhatu_code: str      # Dhatupatha code, e.g. "01.1137"
    aupadeshika: str     # root as listed in the Dhatupatha (accents included), SLP1
    artha: str           # traditional meaning-gloss (SLP1), e.g. "gatO"
    purusha: Purusha
    vacana: Vacana
    lakara: Lakara = Lakara.Lat
    prayoga: Prayoga = Prayoga.Kartari


class VerbGrammar:
    """Derives and indexes the लट्-कर्तरि paradigm of every root in the Dhatupatha."""

    def __init__(self, prakriya_data_dir: str | Path, kosha=None):
        self._vyakarana = Vyakarana()
        data = Data(str(prakriya_data_dir))
        self._entries = {e.code: e for e in data.load_dhatu_entries()}
        self._by_surface: dict[str, list[VerbForm]] = {}
        self._clean_roots: dict[str, str] = {}
        if kosha is not None:
            self._load_clean_roots(kosha)
        self._build_index()

    def _load_clean_roots(self, kosha) -> None:
        """Map each Dhatupatha aupadeshika to its plain-text root.

        A Dhatupatha citation carries accents and it-markers -- गम् is listed
        as `ga\mx~` and कृ as `qukf\Y` -- which is correct data but not a
        root anyone wants shown to them. The Kosha's own DhatuEntry already
        carries the cleaned form, so the display name comes from vidyut rather
        than from stripping anubandhas here by hand.
        """
        for entry in kosha.dhatus():
            try:
                self._clean_roots.setdefault(entry.dhatu.aupadeshika, entry.clean_text)
            except Exception:
                continue

    def clean_root(self, aupadeshika: str) -> str:
        """The plain-text root for display, falling back to the raw citation."""
        return self._clean_roots.get(aupadeshika, aupadeshika)

    def _build_index(self) -> None:
        for code, entry in self._entries.items():
            for lakara, prayoga in INDEXED_PARADIGMS:
                for purusha, vacana in PURUSHA_VACANA:
                    for text in self._derive(entry.dhatu, purusha, vacana, lakara, prayoga):
                        self._by_surface.setdefault(text, []).append(
                            VerbForm(code, entry.dhatu.aupadeshika, entry.artha, purusha, vacana,
                                     lakara, prayoga)
                        )

    def _derive(
        self,
        dhatu,
        purusha: Purusha,
        vacana: Vacana,
        lakara: Lakara = Lakara.Lat,
        prayoga: Prayoga = Prayoga.Kartari,
    ) -> set[str]:
        try:
            tin = Pada.Tinanta(dhatu, prayoga, lakara, purusha, vacana)
            return {r.text for r in self._vyakarana.derive(tin)}
        except Exception:
            return set()

    def lookup(self, surface_slp1: str) -> list[VerbForm]:
        """All readings for an exact surface form, across INDEXED_PARADIGMS.

        Each reading carries its own lakara/prayoga, so a caller that is only
        entitled to act on लट्-कर्तरि must filter rather than assume.
        """
        return self._by_surface.get(surface_slp1, [])

    def suggest(
        self,
        dhatu_code: str,
        purusha: Purusha,
        vacana: Vacana,
        lakara: Lakara = Lakara.Lat,
        prayoga: Prayoga = Prayoga.Kartari,
    ) -> set[str]:
        """Derive the correct form of `dhatu_code` for the given puruSha/vacana.

        lakara/prayoga are explicit rather than implied by the index: this
        derives on demand, so once `_derive` covers more than लट्-कर्तरि a
        caller that did not say which lakara it wanted would silently get
        forms from several merged into one set, and a caller picking one of
        them (karaka_syntax sorts and takes the first) could offer a लङ् form
        to correct a लट् verb. The default keeps every existing caller on
        लट्-कर्तरि exactly as before.
        """
        entry = self._entries.get(dhatu_code)
        if entry is None:
            return set()
        return self._derive(entry.dhatu, purusha, vacana, lakara, prayoga)

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
