# Public dataset licensing and rights

Applies to:

```text
data/roots/
data/root-index.json
data/manifest.json
data/checksums.sha256
```

## Project grant

To the extent the Quran Roots Dictionary Project owns copyright or other
licensable rights in the public dataset's original synthesis, selection,
arrangement, schema expression, and project-authored content, those rights are
offered under **GPL-3.0-only**.

The full license is at repository root in `LICENSE`.

## This is not a blanket relicensing of upstream material

The dataset is evidence-derived. Important upstream rights remain separate.

### Quranic Arabic Corpus

QAC is the canonical source for root identity, Quranic morphology, form
structure, counts, and locations used by the research pipeline.

QAC's public licensing statements are internally inconsistent: its download
page identifies the morphology data as GPL/GPLv3 while also publishing a
no-change condition for verbatim data and requiring attribution in derived
works; its FAQ separately states a non-commercial research-use condition.

For that reason:

**This project does not promise that QAC-derived portions of the public
dataset are cleared for unrestricted commercial reuse.**

Until QAC provides clarification or separate permission, downstream users
should limit QAC-dependent dataset reuse to uses consistent with QAC's
published terms, or obtain permission from QAC.

### Lane / Maqayis / Mufradat structured sources

The structured source repositories used by the project identify themselves as
GPL-3.0. Raw databases are not copied into this public repository.

### Quran Foundation

Raw Quran Foundation API data is not published. The publication transform
removes `context_gloss` recursively from all 1,642 public root files.

## Modification

The Quran Roots project welcomes modifications and evidence-backed correction
PRs to project-owned dictionary analysis. A modified public release should:

- preserve exact case-sensitive QAC root identity unless the upstream QAC data
  itself supports a correction;
- clearly mark substantive semantic changes;
- retain source attribution and third-party notices;
- retain GPL-3.0-only for project-covered material when GPL obligations apply;
- avoid adding raw QF Content without a license that permits redistribution.

## Attribution

When using the dataset, cite the Quran Roots Dictionary release and preserve
the QAC attribution in `THIRD_PARTY_NOTICES.md`.

## No warranty

The dataset is provided without warranty. See GPLv3 sections 15 and 16.
