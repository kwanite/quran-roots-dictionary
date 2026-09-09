# Quran Roots — Current Project Context

**Current date/state:** 2026-08-30  
**Read this file first in a new development chat.**  
**Current work phase:** Front-end/product integration  
**Current semantic dictionary:** v8  
**Current application dataset:** v2.2 — PASS

---

# 1. Current authority hierarchy

For current project state and front-end development, use this order:

```text
1. QURAN_ROOTS_CURRENT_CONTEXT.md
2. QURAN_VERSE_ROOT_EXPLORER_DATA_GUIDE.md
3. FINAL DOCUMENTATION/QURAN_ROOTS_DOCUMENTATION_INDEX_2026-08-30.md
4. FINAL DOCUMENTATION/QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_ADDENDUM_2026-08-30.md
5. FINAL DOCUMENTATION/QURAN_ROOTS_REPRODUCIBILITY_ADDENDUM_2026-08-30.md
6. FINAL DOCUMENTATION/QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_2026-08-25.md
7. FINAL DOCUMENTATION/QURAN_ROOTS_REPRODUCIBILITY_FILE_INDEX_2026-08-25.md
```

The 2026-08-25 documents remain authoritative for how the semantic dictionary was constructed and frozen historically. They must not be rewritten to pretend they always described later v8/application work.

Historical operational docs such as:

```text
QURAN_ROOTS_PROJECT_STATE_2026-08-24.md
QURAN_ROOTS_CONTINUATION_RUNBOOK.md
QURAN_ROOTS_PROJECT_KNOWLEDGE_INDEX.md
```

are retained for history and should not be treated as current project status.

---

# 2. Semantic dictionary state

Canonical QAC roots:

```text
1642
```

The immutable pre-context-enrichment semantic checkpoint remains:

```text
final/numbered_roots/
final/numbered_v7_manifest.json
final/audit/final_freeze_v2/
```

The current application/publication corpus is:

```text
final/numbered_roots_v8/
final/numbered_v8_manifest.json
final/audit/final_freeze_v3/
```

v8 was a deterministic Quran Foundation context-gloss rejoin over v7.

Important v8 facts:

```text
roots:                         1642
Quran examples checked:       9178
roots changed:                 271
examples changed:              429
EMPTY_REJOINABLE:              246
MISMATCH_REJOINABLE:           183
roots byte-identical to v7:   1371
lexical/schema changes:           0
validator hard errors:            0
freeze-v3 gate:               PASS
QF verification matches:      9178
```

v8 did not reopen lexical synthesis. Only permitted `quran_examples[*].context_gloss` values were deterministically rejoined by exact Quran word location.

Do not silently edit v7 or v8. Any later semantic change requires a new version.

---

# 3. Current Quran presentation sources

Canonical application-build source snapshot:

```text
sources/quran-texts/
├── arabic/
│   └── quran-simple-plain.json
├── metadata/
│   └── metadata_surahs.json
└── translations/
    ├── en-arberry-simple.json
    ├── en-asad-simple.json
    ├── en-haleem-with-footnote-tags.json
    └── en-sahih-international-with-footnote-tags.json
```

Arabic source:

```text
Tanzil Uthmani
6236 canonical verses
112 unnumbered ayah:0 opening basmalas
```

Canonical Arabic verse text is never reconstructed from word records.

The four translations each contain exactly 6236 canonical verses with the same `surah:ayah` identity set.

Stable translation IDs:

```text
arberry
asad
abdel_haleem
sahih_international
```

Known translation-source anomaly:

```text
Sahih International
verse 7:143
footnote ID 226798
source footnote body is empty
```

The application dataset preserves this as `MISSING_IN_SOURCE`; do not invent the missing text.

Translation bibliography/licensing metadata still requires manual provenance completion before public redistribution.

---

# 4. Current application dataset

Successful builder:

```text
build_quran_app_dataset_v2_2.py
```

Generated dataset:

```text
output/quran_app_dataset_v2/
```

Build result:

```text
STATUS: PASS

Canonical surahs:                  114
Canonical verses:                 6236
Arabic canonical verses:          6236
Unnumbered Arabic basmalas:        112

QF word records:                 77430
QAC word locations:             77429
QAC segments:                  128219
QAC root-bearing segments:      49968
QAC unique roots:                1642
v8 root artifacts:               1642

QAC words missing from QF:           0
QF words without QAC word record:    1
QF blank transliteration words:      0
```

Generated file counts:

```text
verses/:            114
word_analysis/:     114
root_occurrences/: 1642
```

Root-link integration proof:

```text
root references checked:        49968
missing dictionary targets:         0
ALL ROOT LINKS RESOLVE
```

Known QF-only location:

```text
2:181:14
```

This location has no QAC morphology record and must not be assigned fabricated morphology/root data.

---

# 5. Application data files

```text
output/quran_app_dataset_v2/
├── app_index.json
├── source_manifest.json
├── build_report.json
├── build_report.txt
├── surahs.json
├── translation_catalog.json
├── root_catalog.json
├── arabic_surah_name_differences.csv
├── qf_extra_vs_qac.csv
├── blank_qf_transliteration_words.json
├── verses/
├── word_analysis/
└── root_occurrences/
```

Start any front-end implementation by reading:

```text
output/quran_app_dataset_v2/app_index.json
QURAN_VERSE_ROOT_EXPLORER_DATA_GUIDE.md
```

---

# 6. Identity and join contract

Never join application data by comparing visible text.

Canonical identifiers:

```text
surah
    integer 1..114

verse_key
    surah:ayah
    example: 113:2

word_location
    surah:ayah:word
    example: 113:2:2

segment_location
    surah:ayah:word:segment
    example: 113:2:2:1

root_id
    frozen 4-digit dictionary/application ID
    example: 0049

root
    exact case-sensitive QAC/Buckwalter root
    example: $rr

translation_id
    stable application ID
```

QAC roots are exact and case-sensitive.

Examples:

```text
DHw != dHw
Slw != slw
```

Do not casefold or fuzzy-match roots.

---

# 7. Concatenation rules

Never concatenate word records to construct:

```text
full Arabic verse
full English translation
```

The sole explicit exception is full verse transliteration.

The application dataset may produce:

```text
transliteration_qf
```

by joining QF `transliteration_en` values in exact word-position order.

Therefore:

```text
Arabic verse             dedicated Arabic verse source only
English translation      dedicated translation source only
Full verse translit.     QF ordered word transliterations may be joined
```

---

# 8. Translation independence

Changing the selected full-verse translation must not alter:

```text
QF Arabic word
QF word transliteration
QF contextual English gloss
QAC morphology
QAC lemma
QAC root
root_id
root dictionary
root occurrence list
```

Translation choice is presentation state only.

---

# 9. Direct application lookup model

Verse presentation:

```text
verses/{surah:03d}.json
→ verses_by_key[verse_key]
```

Verse word analysis:

```text
word_analysis/{surah:03d}.json
→ verses_by_key[verse_key]
```

Individual word:

```text
word_analysis/{surah:03d}.json
→ verses_by_key[verse_key]
→ words_by_location[word_location]
```

Root:

```text
root_catalog.json
→ by_id[root_id]
```

Root dictionary:

```text
root catalog record
→ final/numbered_roots_v8/<dictionary_file>
```

Complete root occurrences:

```text
root catalog record
→ output/quran_app_dataset_v2/root_occurrences/<occurrence_file>
```

Order arrays exist only for deterministic display order:

```text
surah_order
verse_order
word_order
root_order
occurrence_order
translation_order
```

Substantive lookup is via keyed maps.

---

# 10. Verified real example — Quran 113:2

```text
113:2:1
Arabic:          مِن
Transliteration: min
QF gloss:        From
Root:            none

113:2:2
Arabic:          شَرِّ
Transliteration: sharri
QF gloss:        (the) evil
Root Arabic:     شرر
Root ID:         0049
QAC root:        $rr
Dictionary:      final/numbered_roots_v8/0049_$rr.json

113:2:3
Arabic:          مَا
Transliteration: mā
QF gloss:        (of) what
Root:            none

113:2:4
Arabic:          خَلَقَ
Transliteration: khalaqa
QF gloss:        He created
Root Arabic:     خلق
Root ID:         1558
QAC root:        xlq
Dictionary:      final/numbered_roots_v8/1558_xlq.json
```

This proves the verse word list can show clickable root links without string matching.

---

# 11. Recommended front-end routes

Verse:

```text
/quran/:surah/:ayah
```

Example:

```text
/quran/113/2
```

Root:

```text
/root/:rootId
```

Example:

```text
/root/0049
```

Prefer numeric root IDs in URLs rather than raw Buckwalter roots because exact roots may contain characters such as `$` and `*`.

Future source viewer:

```text
/source/:sourceType/:sourceId
```

Examples:

```text
/source/lane/22818
/source/maqayis/1986
/source/mufradat/541
```

Do not invent external source URLs. Resolve stable source references against preserved local source data.

---

# 12. Root dictionary structure

Current root corpus:

```text
final/numbered_roots_v8/
```

Representative public lexical hierarchy:

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
    context_gloss
    sense_ids

other_classical_meanings[]
cautions[]
unassigned_or_ambiguous_evidence[]
```

Internal audit structures such as:

```text
qac_form_accounting[]
lane_unit_coverage[]
```

are not ordinary public dictionary prose.

Selected `quran_examples[]` are pedagogical examples and are not the complete occurrence inventory.

---

# 13. Complete root occurrences

Use:

```text
output/quran_app_dataset_v2/root_occurrences/
```

There is one occurrence file per root.

These are derived from all QAC root-bearing segments and enriched by exact QF word location.

They support:

```text
root page
→ complete occurrence list
→ exact verse_key / word_location
→ verse page
```

Do not use selected root dictionary examples as the complete Quran occurrence list.

---

# 14. Lexical-source verification

Primary lexical sources:

```text
Lane
Maqāyīs al-Lugha
Mufradāt Alfāẓ al-Qurʾān
```

Local data:

```text
sources/lane/lexicon.sqlite
sources/arabic-lexicons/db.sqlite
```

Typical stable refs:

```text
lane:entry:22818
maqayis:row:1986
mufradat:row:541
```

A source resolver/viewer remains front-end/integration work.

Current data is sufficient for a structured Lane entry viewer.

An actual scanned Lane printed-page viewer requires a separately verified facsimile/page-image source.

Do not invent page URLs.

Lane historical Quran citations must not be naively converted into modern `surah:ayah` references.

---

# 15. Important source roles

QAC:

```text
canonical root identity
morphology
word/segment locations
form structure
occurrence accounting
```

Quran Foundation:

```text
Arabic word display
word transliteration
contextual English gloss
word position/location
generated full-verse transliteration
```

QF English never creates a dictionary sense by itself.

Lane:

```text
broad Classical lexical evidence
```

Maqāyīs:

```text
root principle / semantic orientation
```

Mufradāt:

```text
Quran-focused lexical distinctions
```

The LLM synthesis is an evidence organizer, not lexical authority.

---

# 16. Front-end loading strategy

For:

```text
/quran/113/2
```

load only:

```text
surahs.json
translation_catalog.json
verses/113.json
word_analysis/113.json
```

When the user clicks root `0049`, navigate to:

```text
/root/0049
```

and load:

```text
root_catalog.json
final/numbered_roots_v8/0049_$rr.json
```

Load:

```text
root_occurrences/0049_$rr.json
```

only when the root page needs the complete occurrence list.

Do not embed complete root dictionary records in every word/verse record.

---

# 17. Front-end implementation order

1. Read `app_index.json`.
2. Implement surah navigation from `surahs.json`.
3. Implement `/quran/:surah/:ayah`.
4. Load `verses/{surah:03d}.json`.
5. Implement translation selection.
6. Load `word_analysis/{surah:03d}.json`.
7. Render words using `word_order`.
8. Link roots with `/root/{root_id}`.
9. Implement root page using `root_catalog.by_id[root_id]`.
10. Load v8 dictionary artifact on demand.
11. Add `root_occurrences/` browser.
12. Link occurrences back to verse routes.
13. Add Lane/Maqāyīs/Mufradāt source resolver.
14. Only then prioritize visual polish.

---

# 18. Never do these things

Do not:

- reconstruct Arabic verse text from QF words;
- reconstruct English verse translations from QF glosses;
- text-match words across sources;
- fuzzy-match roots;
- casefold roots;
- infer root dictionary filenames from visible root text;
- assume every word has one root;
- assume every word has a root;
- make translation selection alter linguistic analysis;
- fabricate QAC data for QF-only `2:181:14`;
- invent Sahih 7:143 footnote 226798;
- invent translation rights/bibliographic metadata;
- invent source-page URLs;
- treat v7/v8 generated artifacts as casually editable source files;
- modify `visualization/` or `build_visualization_data.py` unless explicitly requested.

---

# 19. What remains to build

The core data layer is ready.

Remaining product work is primarily:

```text
front-end verse explorer
translation selector
word-analysis display
root page
root occurrence browser
source-reference resolver/viewer
structured Lane viewer
optional lexical facsimile integration
translation bibliography/license completion
```

Do not restart lexical-data acquisition unless a concrete product requirement shows a real gap.

---

# 20. New-chat startup instruction

A new ChatGPT/LLM development chat should be told:

> Read `QURAN_ROOTS_CURRENT_CONTEXT.md` and `QURAN_VERSE_ROOT_EXPLORER_DATA_GUIDE.md` first. Treat `output/quran_app_dataset_v2/app_index.json` as the application key contract. Use `final/numbered_roots_v8/` as the current root dictionary. Do not use the older dated operational runbooks as current state.

The next phase is front-end development, not semantic dictionary repair.
