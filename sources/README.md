# Reproduction sources

This directory intentionally contains documentation rather than automatically copied third-party raw datasets.

For local reproduction, create:

```text
sources/local/
```

or another ignored working directory and acquire the relevant upstream resources.

Expected research inputs include:

```text
QAC morphology:
  quranic-corpus-morphology-0.4.txt

Lane:
  lexicon.sqlite

Maqayis + Mufradat:
  db.sqlite

Quran Foundation contextual word source:
  qf_wbw_en.json
```

Source roles and project references are documented in `../docs/SOURCE_PROVENANCE.md`.

Do not commit raw Quran Foundation data through this public repository setup.
