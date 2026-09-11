# -*- coding: utf-8 -*-
"""Bridge: turn the engine's own Vidyut analysis of a sentence into CoNLL-U
input for the parser.

This is the DEPLOYMENT path. The treebank experiments score the parser on
gold tags; here the tags come from vidyut.kosha, which is the realistic and
strictly harder setting, because a token may carry several readings and only
one FEATS column exists to hold them.

Two things this must NOT do, both learned the hard way on the first pass:

* **It must not invent a disambiguation.** An earlier version ranked readings
  Prathamā-first and emitted the top one, which stamped `Case=Nom` on every
  ambiguous token -- जनपदे, a locative, came out nominative. Underspecifying
  is honest; guessing nominative manufactures subjects. So a feature is
  emitted only where *every* surviving reading agrees on it.
* **It must not let a तिङन्त homograph outrank an ordinary noun.** रामः is a
  genuine Uttama-dvivacana of रा as well as the name, and the verb reading was
  winning, so रामः was handed to the parser as `VERB Person=1`. The engine
  already solves this with अस्मद्युत्तमः (१.४.१०७) / युष्मद्युपपदे ... मध्यमः
  (१.४.१०५); the same rule is applied here rather than re-invented, so the
  parser sees the view the engine actually holds.
"""
import sys, os
sys.path.insert(0, os.path.abspath("."))
from vidyut.prakriya import Vibhakti, Linga, Vacana, Purusha
from app.karaka_syntax import PRONOUN_MAP, _pronoun_lookup, _strip_it_markers
from app.sanskrit_engine import PRONOMINAL_STEMS

# कृत् suffixes that form a genuinely *verbal* word, which UD tags VERB rather
# than NOUN. Deliberately narrow: suffixes that routinely lexicalise into plain
# adjectives or nouns (yat, tavya, anIyar, kvip, kyap ...) are excluded, because
# tagging those VERB costs more than it gains.
#
# Measured against UD_Sanskrit-UFAL's own annotation, which settles the UD
# convention question empirically: VerbForm=Part is VERB 99 / ADJ 5 / NOUN 3,
# and VerbForm=Conv is VERB 33 / ADJ 1. So VERB is right for both.
VERBAL_KRT = frozenset({"kta", "ktavatu", "Satf", "SAnac", "ktvA", "lyap"})

# क्त्वा / ल्यप् form an *indeclinable* absolutive (क्त्वातोसुन्कसुनः १.१.४०).
# These never lexicalise into a noun, and were measured at 20 gains / 0 losses,
# so a single reading is enough to tag them.
AVYAYA_VERBAL_KRT = frozenset({"ktvA", "lyap"})


# Person carried by each core pronominal stem. अस्मद् is उत्तम (१.४.१०७) and
# युष्मद् मध्यम (१.४.१०५); the deictics and the interrogative are प्रथम.
_PRONOUN_STEM_PERSON = {"asmad": "1", "yuzmad": "2"}


def _pronominal_stem(tok):
    """The core pronominal prātipadika behind this token, if any.

    `PRONOUN_MAP` is 21 hand-written surface forms and covers only the
    nominative-ish ones, so every oblique -- तस्मिन्, तेषु, यस्य, तेन, एतस्य --
    fell through to NOUN even though the Kosha resolves each one's prātipadika
    to तद्/यद्/एतद् perfectly well.

    Unlike the कृदन्त and अव्यय tests above this accepts *any* matching
    reading rather than demanding unanimity, and that is a measured
    difference, not an inconsistency: those two involve open classes where
    गत and कृत are genuinely both participle and adjective, whereas the eight
    stems here are closed-class and distinctive. Measured, any-reading is
    +82/-2 and unanimity only +34/-2 -- the strict rule would discard 48
    correct tags to prevent nothing. Extending the set to the सर्वादि stems
    (सर्व, विश्व, अन्य ...) was also measured and rejected: +2 gains for +6
    losses, because those really do serve as ordinary adjectives.
    """
    lookup = getattr(tok, "kosha_lookup", None)
    if lookup is None:
        return None
    for entry in lookup(tok.text_slp1):
        if not type(entry).__name__.endswith("Subanta"):
            continue
        pratipadika_entry = getattr(entry, "pratipadika_entry", None)
        pratipadika = getattr(pratipadika_entry, "pratipadika", None)
        text = getattr(pratipadika, "text", None)
        if text in PRONOMINAL_STEMS:
            return text
    return None


def _is_unanimous_avyaya(tok):
    """True if *every* nominal reading of this token is an indeclinable.

    The generic NOUN branch sits above the existing `Avyaya` test, so a token
    the Kosha reads as both a particle and some rare declinable homograph was
    reaching NOUN and never being reconsidered -- 87 ADV->NOUN disagreements,
    the largest single bucket once the verb work was done.

    Unanimity rather than "has an avyaya reading", for the same reason the
    कृदन्त test above uses it: accepting any single indeclinable reading is
    +95/-58 measured, while requiring all of them is +37/-2. Nearly the same
    net, a fraction of the damage.
    """
    lookup = getattr(tok, "kosha_lookup", None)
    if lookup is None:
        return False
    flags = []
    for entry in lookup(tok.text_slp1):
        if not type(entry).__name__.endswith("Subanta"):
            continue
        pratipadika_entry = getattr(entry, "pratipadika_entry", None)
        pratipadika = getattr(pratipadika_entry, "pratipadika", None)
        flags.append(bool(getattr(pratipadika, "is_avyaya", False)))
    return bool(flags) and all(flags)


def _verbal_krt(tok):
    """'Conv' for an absolutive, 'Part' for a participle, else None.

    A declinable participle is required to be the *unanimous* reading, not
    merely one available reading. कृत, गत and उक्त are all real past
    participles and also ordinary lexicalised adjectives/nouns, so accepting
    any single participle reading tags every one of them VERB: measured, that
    is 85 gains against 43 losses. Demanding unanimity -- the same rule this
    bridge already applies to FEATS, and for the same reason -- gives 41 gains
    against 3. Absolutives are exempt because they are not ambiguous.

    उक्तम् is the case this gate exists for: the Kosha carries 9 Krdanta(kta)
    readings of it *and* 9 unrelated Basic(ukta) readings -- ukta is also a
    plain adjective ("said, stated"), not just वच्'s participle. Unanimity
    sees both and correctly declines, so उक्तम् stays NOUN. That is the gate
    working as designed, not a missed case -- and exactly the kind of token
    any-reading would have wrongly claimed as one of its 85 gains.
    """
    lookup = getattr(tok, "kosha_lookup", None)
    if lookup is None:
        return None
    krts = []
    for entry in lookup(tok.text_slp1):
        if not type(entry).__name__.endswith("Subanta"):
            continue
        pratipadika_entry = getattr(entry, "pratipadika_entry", None)
        krt = getattr(pratipadika_entry, "krt", None)
        krts.append(_strip_it_markers(str(krt)) if krt is not None else None)
    if not krts:
        return None
    if any(k in AVYAYA_VERBAL_KRT for k in krts):
        return "Conv"
    if all(k in VERBAL_KRT for k in krts):
        return "Part"
    return None

CASE = {Vibhakti.Prathama: "Nom", Vibhakti.Dvitiya: "Acc", Vibhakti.Trtiya: "Ins",
        Vibhakti.Caturthi: "Dat", Vibhakti.Panchami: "Abl", Vibhakti.Sasthi: "Gen",
        Vibhakti.Saptami: "Loc", Vibhakti.Sambodhana: "Voc"}
GENDER = {Linga.Pum: "Masc", Linga.Stri: "Fem", Linga.Napumsaka: "Neut"}
NUMBER = {Vacana.Eka: "Sing", Vacana.Dvi: "Dual", Vacana.Bahu: "Plur"}
PERSON = {Purusha.Prathama: "3", Purusha.Madhyama: "2", Purusha.Uttama: "1"}

def _unanimous(values):
    """The single value all readings agree on, or None if they disagree."""
    s = {v for v in values if v is not None}
    return s.pop() if len(s) == 1 else None

def sentence_has_uttama_madhyama_pronoun(tokens):
    return any(
        (_pronoun_lookup(PRONOUN_MAP, t.text_slp1) or ("Prathama",))[0] in ("Uttama", "Madhyama")
        for t in tokens
    )

def _verb_reading_survives(tok, has_um_pronoun):
    """The engine's own पुरुष-consistency gate (१.४.१०७ / १.४.१०५)."""
    if not tok.verb_readings:
        return False
    if has_um_pronoun:
        return True
    if all(vf.purusha != Purusha.Prathama for vf in tok.verb_readings) and any(
            e.vibhakti == Vibhakti.Prathama for e in tok.nominal_entries):
        return False          # a 1st/2nd-person reading with no अस्मद्/युष्मद् present
    return True

def token_to_row(idx, tok, has_um_pronoun):
    form, lemma = tok.text_deva, (tok.lemma or "_")
    ana = tok.analysis or ""
    feats, ambiguous = [], False

    if _verb_reading_survives(tok, has_um_pronoun):
        upos = "VERB"
        n = _unanimous(NUMBER.get(getattr(v, "vacana", None)) for v in tok.verb_readings)
        p = _unanimous(PERSON.get(getattr(v, "purusha", None)) for v in tok.verb_readings)
        if n: feats.append("Number=" + n)
        if p: feats.append("Person=" + p)
        ambiguous = (n is None or p is None)
    elif _pronoun_lookup(PRONOUN_MAP, tok.text_slp1) is not None:
        upos = "PRON"
        pu, va = _pronoun_lookup(PRONOUN_MAP, tok.text_slp1)
        feats.append("Number=" + {"Eka": "Sing", "Dvi": "Dual", "Bahu": "Plur"}[va])
        feats.append("Person=" + {"Prathama": "3", "Madhyama": "2", "Uttama": "1"}[pu])
    elif _verbal_krt(tok) is not None:
        # A कृदन्त is a verbal form, not a noun. It reached the generic NOUN
        # branch only because the Kosha wraps a declining participle in a
        # Subanta like any other nominal.
        verb_form = _verbal_krt(tok)
        upos = "VERB"
        feats.append("VerbForm=" + verb_form)
        if verb_form == "Part":
            # A participle still declines, so it keeps the case/gender/number
            # the NOUN branch would have emitted -- only the UPOS was wrong.
            c = _unanimous(CASE.get(e.vibhakti) for e in tok.nominal_entries)
            g = _unanimous(GENDER.get(e.linga) for e in tok.nominal_entries)
            n = _unanimous(NUMBER.get(e.vacana) for e in tok.nominal_entries)
            if c: feats.append("Case=" + c)
            if g: feats.append("Gender=" + g)
            if n: feats.append("Number=" + n)
            ambiguous = (c is None or g is None or n is None)
    elif _is_unanimous_avyaya(tok):
        # An indeclinable has no case, gender or number to emit.
        upos = "ADV"
    elif _pronominal_stem(tok) is not None:
        # An oblique pronoun PRONOUN_MAP does not list. It still declines, so
        # it keeps the case/gender/number the NOUN branch would have emitted.
        upos = "PRON"
        feats.append("Person=" + _PRONOUN_STEM_PERSON.get(_pronominal_stem(tok), "3"))
        c = _unanimous(CASE.get(e.vibhakti) for e in tok.nominal_entries)
        g = _unanimous(GENDER.get(e.linga) for e in tok.nominal_entries)
        n = _unanimous(NUMBER.get(e.vacana) for e in tok.nominal_entries)
        if c: feats.append("Case=" + c)
        if g: feats.append("Gender=" + g)
        if n: feats.append("Number=" + n)
        ambiguous = (c is None or n is None)
    elif tok.nominal_entries:
        upos = "NOUN"
        c = _unanimous(CASE.get(e.vibhakti) for e in tok.nominal_entries)
        g = _unanimous(GENDER.get(e.linga) for e in tok.nominal_entries)
        n = _unanimous(NUMBER.get(e.vacana) for e in tok.nominal_entries)
        if c: feats.append("Case=" + c)
        if g: feats.append("Gender=" + g)
        if n: feats.append("Number=" + n)
        ambiguous = (c is None or g is None or n is None)
    elif ana.startswith("Avyaya"):
        upos = "ADV"
    else:
        upos = "X"
        ambiguous = True

    return ("\t".join([str(idx), form, lemma, upos, "_",
                       "|".join(feats) if feats else "_", "_", "_", "_", "_"]),
            ambiguous)

def sentence_to_conllu(tokens, sent_id="s", text=None):
    has_um = sentence_has_uttama_madhyama_pronoun(tokens)
    rows, amb = [], []
    for i, t in enumerate(tokens, 1):
        r, a = token_to_row(i, t, has_um)
        rows.append(r); amb.append(a)
    head = ["# sent_id = " + sent_id]
    if text: head.append("# text = " + text)
    return "\n".join(head + rows) + "\n\n", amb
