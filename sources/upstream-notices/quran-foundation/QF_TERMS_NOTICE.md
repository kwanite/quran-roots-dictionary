# Quran Foundation publication boundary

Developer Terms:

https://api-docs.quran.com/legal/developer-terms/

The current terms prohibit redistribution of QF Content/raw API data without a
separate written license.

The Quran Roots public repository therefore:

- does not include the raw QF word-by-word dataset;
- does not include the QF-derived Quran application dataset;
- removes every `context_gloss` field from the frozen v8 root corpus before
  writing `data/roots/`.

The public build completed on 2026-09-09 reported 9,178 `context_gloss` fields
removed.
