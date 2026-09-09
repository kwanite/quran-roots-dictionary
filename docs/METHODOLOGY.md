# Methodology

## Goal

The project was designed to let a Quran reader move from an attested Quranic word/form to evidence-backed lexical meanings without conflating:

- root-level semantic orientation;
- form-level Quranic senses;
- broader Classical Arabic meanings;
- contextual English glosses;
- a translator's full-verse English choice.

## Canonical identity

The Quranic Arabic Corpus (QAC) is the canonical authority for root identity and morphology.

The frozen project corpus contains:

- 128,219 morphology segment rows;
- 77,429 unique Quran word locations;
- 49,968 root-bearing segment rows;
- 1,642 exact case-sensitive roots;
- 1,602 triliteral roots;
- 40 quadriliteral roots.

Exact case is significant. Roots such as `DHw` and `dHw`, or `Slw` and `slw`, are distinct.

## Evidence architecture

```text
QAC morphology + Quran form inventory
Quran Foundation contextual word evidence
Complete Lane evidence + cross-reference context
Maqayis root evidence
Mufradat Quran-focused evidence
        ↓
deterministic root synthesis packet v3
        ↓
one evidence-grounded LLM synthesis call per root
        ↓
deterministic bookkeeping / safe repair
        ↓
deterministic validator
        ↓
frozen root artifact
```

## Source roles

### Quranic Arabic Corpus

Used for:

- exact root identity;
- word and segment locations;
- lemmas;
- POS and morphology;
- Quran form grouping;
- occurrence accounting.

### Lane

Used for broad Classical Arabic lexical breadth.

Lane evidence was expanded through deterministic cross-reference handling so a root packet would not silently omit meanings located in referenced entries.

### Maqayis al-Lugha

Used mainly for root principles, semantic orientation, and semantic development.

Maqayis alone was not treated as sufficient direct evidence for a numbered Quran-form sense.

### Mufradat Alfaz al-Qur'an

Used for Quran-focused lexical distinctions and Quran-specific semantic guidance.

### Quran Foundation word data

Used as contextual word evidence and for exact Quran word-location joins.

Its English contextual glosses do not independently establish dictionary senses.

### LLM synthesis

The LLM was used as an evidence-grounded synthesizer and organizer, not as an independent lexical authority.

Generated senses and meanings were constrained by supplied source references and then checked by deterministic validation.

## Public forms and senses

The final public hierarchy is:

```text
root orientation
→ Quran-attested forms
→ form-specific senses
→ selected Quran examples
→ broader Classical meanings
→ cautions / ambiguity
```

Each QAC form group is accounted for. A Quran-attested form may carry more than one sense. Broader Classical meanings are kept separate rather than silently promoted into Quranic senses.

## Source references

Stable references in dictionary data include forms such as:

```text
lane:entry:<id>
maqayis:row:<id>
mufradat:row:<id>
```

The synthesizer was instructed not to invent references.

## Lane evidence-loss prevention

The synthesis schema included an internal Lane-unit coverage ledger. Its role was to ensure every supplied primary Lane evidence unit was either linked to a semantic object or explicitly accounted for rather than silently dropped.

This ledger is audit metadata, not ordinary public dictionary prose.

## Deterministic repair philosophy

Post-synthesis repairs were conservative.

Permitted repairs were mechanically provable operations such as:

- collision-free machine-ID canonicalization;
- propagation of repaired IDs through references;
- exact form/accounting realignment when unique;
- occurrence-count correction from already-proven form mappings;
- tightly constrained duplicate handling;
- removal of an invalid optional Quran example when safe.

The pipeline rejected fuzzy lexical guessing and did not casefold root identity.

## Freeze history

The current research corpus is v8.

v8 is a deterministic contextual enrichment of the v7 semantic checkpoint. It did not reopen lexical synthesis. The documented v8 run checked 9,178 Quran examples; 429 examples across 271 roots had contextual gloss values rejoined by exact word location. Lexical/schema changes were zero and the freeze-v3 gate passed with zero validator hard errors.

## Public publication transformation

This public repository does not publish Quran Foundation contextual gloss text.

`build_public_release.py` copies the v8 root artifacts and removes `context_gloss` fields. All original research files remain unchanged.
