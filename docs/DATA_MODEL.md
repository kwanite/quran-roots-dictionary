# Data model

## Root file identity

A public root file uses the frozen numeric root ID plus the exact QAC/Buckwalter root string:

```text
0049_$rr.json
```

The numeric ID is the stable 1-based packet order used by the frozen project. It exists primarily so case-distinct roots can coexist safely on case-insensitive filesystems.

The exact root remains inside the JSON.

## Main public lexical structure

Representative fields:

```text
root
arabic

root_idea
  summary
  development
  source_refs

quranic_forms[]
  public_form_id
  form_group_ids
  headword_arabic
  public_pos_label
  verb_form
  occurrence_count

  senses[]
    sense_id
    definition
    usage_conditions
    source_refs

  quran_examples[]
    verse_key
    word_location
    sense_ids

other_classical_meanings[]
  meaning_id
  headword_arabic
  definition
  usage_conditions
  source_refs

cautions[]
unassigned_or_ambiguous_evidence[]
```

The research corpus may also contain internal accounting structures such as:

```text
qac_form_accounting[]
lane_unit_coverage[]
```

These are retained in the public JSON for auditability unless a future release explicitly defines a reduced consumer schema.

## Quran examples

Dictionary `quran_examples[]` are selected pedagogical examples. They are not the complete root-occurrence inventory.

The public publication transformation removes `context_gloss` while retaining stable Quran locations and sense links.

## Source references

Typical source reference forms:

```text
lane:entry:22818
maqayis:row:1986
mufradat:row:541
```

References are identifiers into the preserved/reproducible source layer. Do not convert them to guessed external URLs.

## Exact identifiers

Never:

- casefold roots;
- fuzzy-match roots;
- fuzzy-match source references;
- infer a filename from visible Arabic text.

Use `data/root-index.json`.
