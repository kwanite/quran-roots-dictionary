# Source provenance

The research pipeline uses several sources with different roles. This
repository does not redistribute their raw datasets by default.

## Quranic Arabic Corpus (QAC)

Project role:

- canonical root identity;
- morphology;
- word/segment locations;
- form structure;
- occurrence accounting.

Research source:

- https://corpus.quran.com/download/
- https://corpus.quran.com/documentation/
- https://corpus.quran.com/license.jsp
- https://corpus.quran.com/faq.jsp

The project used morphology v0.4. See `LICENSING.md` for the upstream
GPL/non-commercial/no-change inconsistency.

The raw morphology file is not included.

## Lane's Arabic-English Lexicon

Project role: broad Classical Arabic lexical evidence.

Structured source:

https://github.com/laneslexicon/LexiconDatabase

The upstream repository identifies itself as GPL-3.0.

Expected research database:

```text
sources/lane/lexicon.sqlite
```

The raw database is not included.

## Maqayis al-Lugha and Mufradat Alfaz al-Qur'an

Structured source:

https://github.com/wizsk/arabic_lexicons

The upstream repository states that it is GPL-3.0.

Expected research database:

```text
sources/arabic-lexicons/db.sqlite
```

Roles:

- Maqayis: root principle / semantic orientation;
- Mufradat: Quran-focused lexical distinctions.

The raw database is not included.

## Quran Foundation / Quran.com

Project role: contextual Quran word evidence used during research.

Developer Terms:

https://api-docs.quran.com/legal/developer-terms/

Current terms prohibit redistribution of QF Content/raw API data without a
separate written license.

The public root release therefore excludes raw QF datasets and recursively
removes `context_gloss` from public root JSON.

## OpenAI

The LLM synthesis stage used the OpenAI API as an evidence-grounded
synthesizer/organizer.

Services Agreement:

https://openai.com/policies/services-agreement/

The agreement assigns Output rights to the API customer as between the
customer and OpenAI, to the extent permitted by law, while leaving the
customer responsible for Input rights and downstream use.

## Licensing files

See:

```text
LICENSE
LICENSE_SCOPE.md
THIRD_PARTY_NOTICES.md
data/DATA_LICENSE.md
docs/LICENSING.md
```
