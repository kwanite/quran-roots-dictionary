# Quran Roots — Reproducibility Addendum for v8 / Application Dataset

**Date:** 2026-08-30  
**Companion to:** `QURAN_ROOTS_REPRODUCIBILITY_FILE_INDEX_2026-08-25.md`

This addendum records files introduced after the semantic-freeze file index.

---

# 1. Current v8 application dictionary

```text
final/numbered_roots_v8/
final/numbered_v8_manifest.json
final/qf_context_rejoin_v8/
final/audit/final_freeze_v3/
```

Relevant scripts:

```text
rejoin_qf_context_glosses_v8.py
audit_final_numbered_roots_freeze_v3.py
```

---

# 2. Canonical Quran presentation inputs

```text
sources/quran-texts/arabic/quran-simple-plain.json
sources/quran-texts/metadata/metadata_surahs.json

sources/quran-texts/translations/en-arberry-simple.json
sources/quran-texts/translations/en-asad-simple.json
sources/quran-texts/translations/en-haleem-with-footnote-tags.json
sources/quran-texts/translations/en-sahih-international-with-footnote-tags.json
```

These are source snapshots and should be preserved.

---

# 3. Application builder

```text
build_quran_app_dataset_v2_2.py
```

This is the successful deterministic builder.

Earlier v2/v2.1/v2.2 failed attempts may be retained for provenance but are not current build authority.

---

# 4. Generated application dataset

```text
output/quran_app_dataset_v2/
```

Important files:

```text
app_index.json
source_manifest.json
build_report.json
build_report.txt
surahs.json
translation_catalog.json
root_catalog.json
qf_extra_vs_qac.csv
arabic_surah_name_differences.csv
blank_qf_transliteration_words.json
```

Generated collections:

```text
verses/            114 files
word_analysis/     114 files
root_occurrences/ 1642 files
```

---

# 5. Build proof

Observed successful build:

```text
Canonical verses:              6236
QF word records:              77430
QAC word locations:           77429
QAC root-bearing segments:    49968
QAC unique roots:              1642
v8 root artifacts:             1642
QF words without QAC record:      1
QF blank transliterations:        0
```

Observed root-target verification:

```text
Root references checked:       49968
Missing dictionary targets:        0
ALL ROOT LINKS RESOLVE
```

---

# 6. Application source manifest

The builder writes:

```text
output/quran_app_dataset_v2/source_manifest.json
```

This is the first machine-readable provenance file to inspect when reproducing the application dataset. It records input paths and SHA-256 hashes.

---

# 7. Current implementation documentation

```text
QURAN_ROOTS_CURRENT_CONTEXT.md
QURAN_VERSE_ROOT_EXPLORER_DATA_GUIDE.md
FINAL DOCUMENTATION/QURAN_ROOTS_DOCUMENTATION_INDEX_2026-08-30.md
FINAL DOCUMENTATION/QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_ADDENDUM_2026-08-30.md
FINAL DOCUMENTATION/QURAN_ROOTS_REPRODUCIBILITY_ADDENDUM_2026-08-30.md
FINAL DOCUMENTATION/QURAN_ROOTS_KEY_FILES_2026-08-30.csv
```

---

# 8. Preservation rule

Preserve both:

```text
source inputs
generated application dataset
successful builder
source manifest/build report
current documentation
```

Do not delete older semantic-freeze files. The application layer is additive to the semantic corpus history.
