# Quran Roots — Current Documentation Index

**Date:** 2026-08-30  
**Status:** Semantic dictionary v8 + application dataset v2.2 ready for front-end integration.

This file supersedes the 2026-08-25 documentation index for determining **current project state**. The 2026-08-25 index and method documents remain preserved as historical semantic-freeze documentation.

---

# 1. Read first for current development

```text
QURAN_ROOTS_CURRENT_CONTEXT.md
QURAN_VERSE_ROOT_EXPLORER_DATA_GUIDE.md
output/quran_app_dataset_v2/app_index.json
```

Use these for current front-end development state, IDs, joins, routes, and data locations.

---

# 2. Current application/publication dictionary

```text
final/numbered_roots_v8/
final/numbered_v8_manifest.json
final/audit/final_freeze_v3/
```

v8 is the current application corpus.

The immutable v7 semantic checkpoint remains:

```text
final/numbered_roots/
final/numbered_v7_manifest.json
final/audit/final_freeze_v2/
```

---

# 3. Current application dataset

```text
build_quran_app_dataset_v2_2.py
output/quran_app_dataset_v2/
```

Build status:

```text
PASS
6236 canonical verses
77430 QF words
77429 QAC words
49968 root-bearing segments
1642 roots
1642 v8 dictionary files
49968 root links checked
0 missing dictionary targets
```

---

# 4. Current Quran presentation sources

```text
sources/quran-texts/arabic/quran-simple-plain.json
sources/quran-texts/metadata/metadata_surahs.json

sources/quran-texts/translations/en-arberry-simple.json
sources/quran-texts/translations/en-asad-simple.json
sources/quran-texts/translations/en-haleem-with-footnote-tags.json
sources/quran-texts/translations/en-sahih-international-with-footnote-tags.json
```

---

# 5. Current application data guide

```text
QURAN_VERSE_ROOT_EXPLORER_DATA_GUIDE.md
```

This is the front-end implementation contract.

---

# 6. Semantic method/provenance authority

Original semantic-freeze method:

```text
FINAL DOCUMENTATION/QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_2026-08-25.md
```

Current addendum:

```text
FINAL DOCUMENTATION/QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_ADDENDUM_2026-08-30.md
```

Together they describe the semantic freeze, v8 contextual enrichment, and application integration boundary.

---

# 7. Reproducibility/file authority

Original semantic file map:

```text
FINAL DOCUMENTATION/QURAN_ROOTS_REPRODUCIBILITY_FILE_INDEX_2026-08-25.md
```

Current application addendum:

```text
FINAL DOCUMENTATION/QURAN_ROOTS_REPRODUCIBILITY_ADDENDUM_2026-08-30.md
```

Current key-file list:

```text
FINAL DOCUMENTATION/QURAN_ROOTS_KEY_FILES_2026-08-30.csv
```

---

# 8. Historical documents

Retain but do not use for current counts/status:

```text
QURAN_ROOTS_PIPELINE_SUMMARY.md
QURAN_ROOTS_USER_EXPERIENCE_GOALS.md
QURAN_ROOTS_PROJECT_STATE_2026-08-24.md
QURAN_ROOTS_CONTINUATION_RUNBOOK.md
QURAN_ROOTS_PROJECT_KNOWLEDGE_INDEX.md

FINAL DOCUMENTATION/QURAN_ROOTS_DOCUMENTATION_INDEX_2026-08-25.md
```

They remain useful for provenance and history.

---

# 9. Current next phase

```text
FRONT-END DEVELOPMENT
```

Priority sequence:

```text
verse route
translation selector
word/root list
root route
root occurrence navigation
source resolver/viewer
```

Do not reopen semantic repair merely to continue product work.
