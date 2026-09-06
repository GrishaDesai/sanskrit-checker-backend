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
from app.karaka_syntax import PRONOUN_MAP, _pronoun_lookup

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
