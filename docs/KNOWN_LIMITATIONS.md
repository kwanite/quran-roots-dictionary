# Known limitations

## LLM-generated synthesis

Definitions and semantic organization were synthesized by an LLM from supplied evidence. Deterministic validation can enforce structural/evidence constraints but cannot prove every prose judgment is philologically optimal.

Contributions correcting semantic judgments are therefore welcome when backed by evidence.

## Selected Quran examples

`quran_examples[]` are selected examples, not exhaustive root occurrences.

## Quran Foundation publication boundary

The research v8 corpus contains Quran Foundation-derived `context_gloss` values.

The public-release builder removes these values, so the public website shows Quran locations and sense links without those English contextual glosses.

## Source viewers

Stable Lane/Maqayis/Mufradat source references exist, but this repository does not yet ship a full source-entry browser or facsimile viewer.

## Historical source citation conventions

Lane may contain historical Quran citation conventions. They should not be naively converted to modern `surah:ayah` references without independent support.

## Licensing

The final repository/data license remains a publication blocker until the upstream-source and generated-dataset rights are reviewed and documented.

## No byte-identical LLM reproducibility guarantee

Deterministic evidence preparation can be reproduced. A fresh LLM synthesis may produce different wording or semantic organization.
