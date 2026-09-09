# Quran Roots Dictionary

A structured, auditable Quranic Arabic root dictionary built from Quranic
morphology and Classical Arabic lexical evidence.

## What this repository contains

The public release is organized around three goals:

1. **Use the data** — download one JSON file per Quranic root.
2. **Understand and verify the method** — inspect provenance, methodology,
   validation rules, and maintained pipeline scripts.
3. **Contribute corrections** — propose evidence-backed changes through issues
   and pull requests.

The canonical project corpus contains **1,642 exact case-sensitive Quranic
Arabic Corpus (QAC) roots**. Root identity is preserved exactly; case-distinct
Buckwalter roots are not merged. Stable four-digit IDs are used in filenames
so case-distinct roots can coexist on case-insensitive filesystems.

## Repository layout

```text
data/
  roots/                  1,642 public root JSON files
  root-index.json         Root ID / filename / Arabic lookup
  manifest.json           Public-release metadata
  checksums.sha256        SHA-256 checksums
  DATA_LICENSE.md         Dataset rights and QAC caveat
  schema/root.schema.json Structural schema

docs/
  METHODOLOGY.md
  DATA_MODEL.md
  SOURCE_PROVENANCE.md
  VALIDATION.md
  REPRODUCIBILITY.md
  AI_SYNTHESIS.md
  KNOWN_LIMITATIONS.md
  CONTRIBUTING_DATA_CORRECTIONS.md
  LICENSING.md
  research-record/

pipeline/
  Curated maintained construction and validation scripts

scripts/
  build_public_release.py
  validate_public_release.py

site/
  Static browser for GitHub Pages
```

## Evidence architecture

```text
QAC morphology + Quran form inventory
Quran Foundation contextual word evidence
Lane lexical evidence + cross-reference context
Maqayis root evidence
Mufradat Quran-focused evidence
        ↓
deterministic root synthesis packet
        ↓
one evidence-grounded LLM synthesis per root
        ↓
deterministic repair / bookkeeping
        ↓
deterministic validation
        ↓
frozen root dictionary
```

Evidence roles are deliberately separated:

- **QAC** — canonical root identity, morphology, form structure, counts and
  Quran locations.
- **Lane** — broad Classical Arabic lexical evidence.
- **Maqayis** — root principle and semantic orientation.
- **Mufradat** — Quran-focused lexical distinctions.
- **Quran Foundation** — contextual word evidence; it does not independently
  establish dictionary senses.
- **LLM** — evidence-grounded synthesis/organization, not a lexical authority.

See `docs/METHODOLOGY.md`.

## Quran Foundation publication boundary

The research v8 corpus contains Quran Foundation-derived
`quran_examples[*].context_gloss` values.

The public release builder creates a publication copy and recursively removes
`context_gloss`. The completed public build removed **9,178** such fields.

Raw Quran Foundation datasets are not included.

## Quick use

Each root is stored as:

```text
data/roots/<4-digit-id>_<exact-QAC-root>.json
```

Use `data/root-index.json` rather than guessing filenames.

## Website

The `site/` folder is a dependency-free static browser. GitHub Actions can
publish it to GitHub Pages together with the public root data.

## Contributions

Issues and pull requests are welcome. Semantic corrections must be
evidence-backed and pass automated validation.

See `CONTRIBUTING.md` and `docs/CONTRIBUTING_DATA_CORRECTIONS.md`.

## License and upstream rights

Project-controlled copyrightable material is offered under
**GPL-3.0-only**. See `LICENSE` and `LICENSE_SCOPE.md`.

This does **not** override third-party source rights.

Important QAC caveat: QAC currently publishes licensing statements that are
not fully consistent with one another. Its download/license pages identify
GPL/GPLv3, while its download terms contain an additional no-change condition
for verbatim source data and its FAQ describes research use as non-commercial.

Accordingly, this project does **not** claim that QAC-derived parts of the
public dataset are cleared for unrestricted commercial reuse.

Read:

- `docs/LICENSING.md`
- `THIRD_PARTY_NOTICES.md`
- `data/DATA_LICENSE.md`

Raw QAC, Lane, Arabic Lexicons, and Quran Foundation databases are not
redistributed by this public repository.
