# Third-party notices

This repository was built from, or with reference to, several external
resources. The public repository does not automatically redistribute their raw
datasets.

## Quranic Arabic Corpus (QAC)

**Project role:** canonical Quranic root identity, morphology, form structure,
locations, and occurrence accounting.

**Version used by the research project:** morphology v0.4.

**Copyright identified by the upstream download page:**  
Copyright (C) 2011 Kais Dukes.

Upstream pages:

- https://corpus.quran.com/download/
- https://corpus.quran.com/license.jsp
- https://corpus.quran.com/faq.jsp

The QAC download page identifies the morphology data as GNU GPL and links GPL
version 3. It also publishes additional terms requiring clear QAC attribution
and reproduction of the source notice in derived/substantial works.
Separately, the FAQ describes research use as non-commercial.

Required attribution used by this project:

> Quranic morphology/root data is derived from the Quranic Arabic Corpus,
> corpus.quran.com, created by Kais Dukes and contributors.

The public release does not contain a verbatim copy of the QAC morphology
download.

## Lane's Arabic-English Lexicon — LexiconDatabase

Project role: broad Classical Arabic lexical evidence.

Upstream repository:

https://github.com/laneslexicon/LexiconDatabase

The upstream repository identifies the LexiconDatabase project as GPL-3.0.

The public Quran Roots repository does not redistribute `lexicon.sqlite`.
Stable `lane:entry:*` references and synthesized lexical analysis may remain in
the root data.

## Arabic Lexicons — Maqayis / Mufradat

Project roles:

- Ibn Faris, *Maqayis al-Lugha*: root principle / semantic orientation.
- al-Raghib al-Isfahani, *Mufradat Alfaz al-Qur'an*: Quran-focused lexical
  distinctions.

Upstream repository:

https://github.com/wizsk/arabic_lexicons

The upstream repository states that the project is released under GPL-3.0.

The public Quran Roots repository does not redistribute `db.sqlite`. Stable
`maqayis:row:*` and `mufradat:row:*` references and synthesized analysis may
remain.

## Quran Foundation / Quran.com APIs

Project role: contextual Quran word evidence during research and the historical
v8 context-gloss verification/rejoin.

Developer Terms:

https://api-docs.quran.com/legal/developer-terms/

The current terms prohibit redistribution of QF Content/raw API data without a
separate written license.

The public release therefore excludes raw Quran Foundation datasets and removes
every `context_gloss` field from the frozen v8 root files before publication.

## OpenAI API

The root-dictionary synthesis stage used the OpenAI API as an
evidence-grounded organizer/synthesizer.

Current Services Agreement:

https://openai.com/policies/services-agreement/

As between the customer and OpenAI, the agreement assigns Output rights to the
customer to the extent permitted by applicable law. It also leaves the customer
responsible for having the rights needed for Input and for downstream use of
Output.

No OpenAI model weights, proprietary service code, or raw API service assets
are redistributed in this repository.

## Classical works and editions

Lane, Ibn Faris, and al-Raghib are historical lexical sources. This project
does not assume that every modern edition, transcription, database encoding,
scan, or structured representation of those works is free of separate rights.
The structured database projects used in the pipeline retain their own
licenses as described above.
