# Licensing research and publication decision

**Reviewed:** 2026-09-09

This document records the licensing decision used for the first public Quran
Roots Dictionary repository. It is a project record, not legal advice.

## Decision

The repository uses a scoped **GPL-3.0-only** model for material whose rights
are controlled by the Quran Roots Dictionary Project.

Third-party source rights are preserved and are not silently relicensed.

The public root dataset carries an explicit QAC caveat because QAC's own
current public statements are internally inconsistent about modification and
commercial use.

## Source-by-source findings

### Quranic Arabic Corpus

Official pages:

- https://corpus.quran.com/download/
- https://corpus.quran.com/license.jsp
- https://corpus.quran.com/faq.jsp

Findings:

1. Morphology v0.4 is identified as GNU GPL.
2. The linked license page is GPL version 3.
3. The download page also publishes a no-change condition for verbatim source
   data and requires QAC attribution/notices in derived or substantial works.
4. The FAQ separately describes the research data as non-commercial.

Those statements do not fit cleanly with ordinary GPLv3 permissions. The
project cannot determine which statement QAC intends to control without
clarification from QAC.

Publication consequence:

- raw QAC morphology is not redistributed;
- QAC attribution is preserved prominently;
- only project-controlled rights are licensed by this repository;
- the project does not claim that QAC-derived dataset content is commercially
  unrestricted;
- commercial QAC-dependent reuse should obtain clarification/permission.

### Lane LexiconDatabase

Repository:

https://github.com/laneslexicon/LexiconDatabase

The repository identifies itself as GPL-3.0.

Publication consequence:

- raw `lexicon.sqlite` is not redistributed;
- `lane:entry:*` source references remain;
- GPL-3.0-only is compatible with the project's conservative licensing choice.

### Arabic Lexicons — Maqayis and Mufradat

Repository:

https://github.com/wizsk/arabic_lexicons

The upstream README states that the project is released under GPL-3.0.

Publication consequence:

- raw `db.sqlite` is not redistributed;
- `maqayis:row:*` and `mufradat:row:*` references may remain;
- GPL-3.0-only is compatible with the project's conservative licensing choice.

### Quran Foundation

Developer Terms:

https://api-docs.quran.com/legal/developer-terms/

The current terms, last updated 2026-08-26, prohibit redistribution of QF
Content/raw API data without a separate written license.

Research-corpus fact:

The v8 root corpus deterministically verified/rejoined
`quran_examples[*].context_gloss` values without changing lexical/schema
content.

Publication consequence:

- raw QF datasets are excluded;
- `build_public_release.py` recursively removes all `context_gloss` fields;
- the completed public build reported 9,178 such fields removed;
- the larger QF-derived application dataset is not included.

### OpenAI synthesis output

Services Agreement:

https://openai.com/policies/services-agreement/

For API customers, OpenAI states that as between the customer and OpenAI and
to the extent permitted by law, the customer owns Output and OpenAI assigns
its rights, if any, in Output to the customer. The customer remains
responsible for Input rights and downstream use.

Publication consequence:

No separate OpenAI redistribution license is required merely because the
dictionary synthesis stage used the API. This does not solve upstream
source-rights issues in the model Input, which are handled separately.

## Why GPL-3.0-only

GPL-3.0-only was selected for project-controlled material because:

- QAC explicitly links GPLv3 despite its additional inconsistent wording;
- Lane's structured database is GPL-3.0;
- the Maqayis/Mufradat structured database project is GPL-3.0;
- a GPLv3 project license avoids falsely presenting a permissive license as
  though it could override upstream copyleft rights;
- GPL supports public inspection, forks, modification, and pull requests.

`GPL-3.0-only` is used rather than `GPL-3.0-or-later` because the upstream
resources found in this review identify GPL-3.0 and do not provide a basis for
assuming an "or later" grant.

## Ready for public Git hosting

- project code and method documentation;
- static website;
- publication scripts and validator;
- 1,642-root publication transform with all `context_gloss` fields removed;
- source refs and provenance/freeze reports that do not reproduce restricted
  raw QF content.

## Intentionally excluded

- raw Quran Foundation API datasets;
- original v8 `context_gloss` values;
- raw QAC morphology download;
- Lane SQLite database;
- Arabic Lexicons SQLite database;
- Quran translation/application datasets not separately cleared for this repo;
- raw OpenAI Batch response archives.

## Remaining caveat

The repository is ready to publish with these notices, but the root dataset
should **not** be marketed as commercially unrestricted unless QAC clarifies
its conflicting public licensing language or gives separate permission.

The independently authored project code can be used under GPL-3.0-only.
