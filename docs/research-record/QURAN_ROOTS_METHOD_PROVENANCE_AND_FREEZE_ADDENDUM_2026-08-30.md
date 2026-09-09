# Quran Roots — Method / Provenance Addendum: v8 and Application Integration

**Date:** 2026-08-30  
**Companion to:** `QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_2026-08-25.md`

This addendum records work completed after the 2026-08-25 semantic freeze documentation. It does not rewrite the historical freeze record.

---

# 1. v8 contextual-enrichment release

v7 remains the immutable semantic checkpoint:

```text
final/numbered_roots/
final/numbered_v7_manifest.json
final/audit/final_freeze_v2/
```

v8 is the current application/publication corpus:

```text
final/numbered_roots_v8/
final/numbered_v8_manifest.json
final/audit/final_freeze_v3/
```

v8 was produced deterministically with no LLM/API calls.

Permitted change scope:

```text
quranic_forms[*].quran_examples[*].context_gloss
```

Exact preserved QF word locations were used for rejoin.

Results:

```text
roots:                         1642
examples checked:              9178
changed roots:                  271
changed examples:               429
roots byte-identical to v7:    1371
lexical/schema changes:            0
validator hard errors:             0
freeze-v3:                      PASS
independent QF matches:          9178
```

v8 must not be described as a new LLM semantic synthesis. It is deterministic contextual enrichment of the frozen semantic corpus.

---

# 2. Verse/application source integration

A dedicated Quran publication layer was added under:

```text
sources/quran-texts/
```

It contains:

```text
Arabic Tanzil verse text
114-surah metadata
Arberry translation
Muhammad Asad translation
M. A. S. Abdel Haleem translation
Sahih International translation
```

All four translations and the dedicated Arabic corpus align on the same 6236 canonical `surah:ayah` identities.

Full Arabic verse text is never reconstructed from QF word data.

Full translations are never reconstructed from word glosses.

Full verse transliteration is the explicit exception: ordered QF word transliterations may be joined to form a generated `transliteration_qf` line.

---

# 3. Deterministic application build

Builder:

```text
build_quran_app_dataset_v2_2.py
```

Output:

```text
output/quran_app_dataset_v2/
```

The builder uses no LLM.

It joins sources only by canonical IDs/locations.

Build result:

```text
PASS

6236 canonical verses
77430 QF words
77429 QAC word locations
128219 QAC segments
49968 root-bearing segments
1642 exact roots
1642 v8 root artifacts
0 QAC words missing from QF
1 QF-only word location
0 blank QF transliterations
```

Root-reference integrity:

```text
49968 root references checked
0 missing v8 dictionary targets
```

---

# 4. Stable application identity

The application layer uses:

```text
verse_key        surah:ayah
word_location    surah:ayah:word
segment_location surah:ayah:word:segment
root_id          frozen four-digit dictionary ID
root             exact case-sensitive QAC root
translation_id   stable application translation ID
```

No text matching or fuzzy root matching is part of the data contract.

---

# 5. Separation of layers

The application architecture preserves these boundaries:

```text
VERSE PRESENTATION
    Arabic verse
    selected translation
    generated QF verse transliteration

STATIC WORD ANALYSIS
    QF word Arabic
    QF word transliteration
    QF contextual gloss
    QAC morphology
    exact roots[]

ROOT DICTIONARY
    final/numbered_roots_v8/

COMPLETE ROOT OCCURRENCES
    output/quran_app_dataset_v2/root_occurrences/

SOURCE VERIFICATION
    Lane / Maqāyīs / Mufradāt local evidence
```

Changing translation selection changes only presentation translation text.

---

# 6. Known non-blocking source anomalies

QF-only location:

```text
2:181:14
```

Do not fabricate QAC morphology for it.

Sahih International:

```text
7:143
footnote ID 226798
source footnote body empty
```

The generated application dataset preserves this explicitly rather than inventing text.

---

# 7. Current project phase

The principal data-integration blockers for the basic verse/root explorer are resolved.

The project is now in front-end/product integration.

See:

```text
QURAN_ROOTS_CURRENT_CONTEXT.md
QURAN_VERSE_ROOT_EXPLORER_DATA_GUIDE.md
```

for current implementation contracts.
