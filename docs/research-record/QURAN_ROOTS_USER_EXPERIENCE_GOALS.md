# Quran Roots Dictionary — User Experience & Data Design Goals

_Last updated: 2026-08-23_

## Purpose of this document

This file complements:

- `QURAN_ROOTS_PIPELINE_SUMMARY.md` — what data we have and how it is built
- `QURAN_ROOTS_LLM_CALL_PLAN.md` — what each LLM stage is supposed to do

This document answers a different question:

> **What should the final product help a Quran reader see, understand, and independently evaluate?**

The pipeline is being structured around those user goals.

---

# 1. Primary user goal

The root dictionary should help an ordinary Quran reader move from:

```text
a translated verse
```

to:

```text
the actual Arabic word
→ its Quranic form
→ the meanings that form can carry
→ examples of those meanings in the Quran
→ broader classical meanings
→ source evidence and cautions
```

The purpose is **not** merely to tell the user what a translator chose.

The user should be able to ask:

> Is this English rendering plausible for this Arabic word, in this form and context?

and inspect enough lexical evidence to form an informed view.

This is why the project separates:

```text
Arabic lexical evidence
from
English translation choices
```

---

# 2. What the user should be able to do

## From a Quran verse

A user should be able to click an Arabic word or root and open a dictionary page for that root.

The page should preserve the verse they came from and automatically emphasize the relevant Quran form.

Conceptually:

```text
Verse
  ↓ click word
Root page
  ↓
Relevant form opened / highlighted
  ↓
Originating verse shown first
```

The user should not have to search through the entire root page to rediscover the word they clicked.

---

## See the root idea without confusing it with a translation

At the top of the page, the user should see a short explanation of the root's broader semantic idea or development.

Example:

```text
كتب

Root idea

bringing / joining together
→ joining letters
→ writing
→ written fixation
→ prescription / decree
```

This is useful for understanding how apparently different meanings may relate.

But the product must **not** imply:

> every Quranic word from كتب literally means "to join."

Root-level semantic development and direct form-level meanings must remain separate.

---

## See the actual forms and words found in the Quran

The core of the page should be organized by Quran-attested form, not by one undifferentiated list of root meanings.

Example:

```text
كتب

كَتَبَ
Verb · Form I

كِتَاب
Noun

كَاتِب
Noun / adjective

Form III occurrence

Form VIII occurrence

مَكْتُوب
```

This matters because one root can contain forms with substantially different meanings.

A particularly important example is:

```text
أَتَى   Form I   → come / arrive / approach

آتَى    Form IV  → give / grant / bestow
```

A root-only English meaning list would blur this distinction and could mislead users.

### Keep the clicked Quran form separate from the dictionary headword

The exact Quran surface form the user clicked may differ from the normalized dictionary citation form.

The page should preserve both:

```text
clicked Quran word / surface
normalized Quran-form or dictionary headword
```

The software must not silently turn a corpus lemma string into a polished classical headword. If headword normalization is uncertain, preserve the QAC identity internally and surface a caution rather than inventing a form.

Every Quran-attested QAC form group must remain accounted for even when several internal groups are intentionally merged into one cleaner public dictionary form.

---

## See multiple meanings for the same Quran form

The product should not pretend that one Arabic form always equals one English word.

Example:

```text
كَتَبَ

1. to write or record
2. to prescribe or make obligatory
3. to decree or determine
4. to enroll / include in certain expressions
```

This allows the user to see that translation depends on context while still being constrained by real lexical evidence.

---

## See Quran examples for distinct meanings

Each important meaning should have examples from the Quran where possible.

The user-facing presentation should show:

```text
full Arabic verse
full selected English translation
highlighted target word
```

and optionally:

```text
Word gloss: "is prescribed"
```

The public citation should look like:

```text
Al-Baqarah 2:183
```

not an internal coordinate such as:

```text
2:183:4
```

Internal `word_location` values remain useful to the software, but should not be the main user-facing citation.

Examples should be chosen to illustrate **different senses or constructions**, not merely because they are the first occurrences in corpus order. The originating verse from which the user opened the root page should still be shown first or prominently.

---

## Change Quran translation without changing the dictionary

The lexical dictionary should not be tied to one English Quran translation.

The root dataset should store only stable references such as:

```json
{
  "verse_key": "2:183",
  "word_location": "2:183:4"
}
```

Full translations should live separately.

This allows a user to switch from one translation to another instantly while the Arabic lexical analysis stays unchanged.

The product principle is:

> **A Quran translation is contextual evidence for the reader, not the source of the Arabic dictionary meaning.**

---

## See broader Classical Arabic meanings without clutter

Lane contains many legitimate Classical Arabic meanings that may not occur in the Quran.

Those meanings should not be discarded.

But they also should not overwhelm the main Quran-focused experience.

They should appear under something like:

```text
Other classical meanings
```

collapsed by default and clearly labeled as **not necessarily attested in the Quran**.

A broader Classical Arabic form or sense must never be presented under “Forms and meanings found in the Quran” unless the Quran-form mapping supports that claim.

This gives the user access to the wider lexical family while keeping the primary page focused on meanings relevant to Quran forms.

---

## See uncertainty and disagreement clearly

The product should not hide important limitations.

A **Cautions** section should surface issues such as:

- ambiguous lexical evidence
- competing interpretations
- grammatical restrictions
- meanings limited to a construction
- weak or incomplete source coverage
- shared Mufradāt passages that cannot be assigned confidently
- important source disagreement

The goal is not to make the dictionary look more certain than the evidence really is.

Coverage limitations should also be visible. If a root lacks Lane, Maqāyīs, or another expected source, the page should not infer that the missing source agrees; it should simply state the relevant evidence limitation in plain language when it materially affects interpretation.

---

## Inspect sources without forcing source names into definitions

Definitions should read naturally:

```text
to prescribe or make obligatory
```

not:

```text
Lane says this means to prescribe...
```

Source provenance should be available through source chips / expandable evidence:

```text
Lane
Maqāyīs
Mufradāt
QAC
Quran context
```

The normal user sees clean dictionary prose.

A user who wants to investigate further can open the evidence behind it.

---

# 3. Public-facing language should be simple

The dictionary is intended for general readers, not only linguists or corpus specialists.

Avoid technical internal terminology in the normal interface.

Prefer:

```text
Verb · Form VIII
Noun
83 occurrences
Examples from the Quran
Other classical meanings
Cautions
Sources
```

Avoid exposing by default:

```text
QAC lemma ID
POS code
lexeme
IMPF
raw Buckwalter
internal source-unit IDs
```

Those details can remain in the data and advanced evidence views.

The user should not need to understand the data pipeline in order to use the dictionary.

---

# 4. Why the data is structured this way

The current architecture follows directly from the usability goals.

## QAC provides the user-visible Quran form skeleton

QAC answers:

```text
What form actually occurs in the Quran?
How often?
Where?
What morphology does it have?
```

This is why Quran forms are built deterministically before meanings are assigned.

---

## Lane provides breadth

Lane answers:

```text
What meanings are attested in Classical Arabic for this root/form family?
```

Its evidence is kept exhaustive so that rare but legitimate meanings do not silently disappear.

This supports the user-facing **Other classical meanings** section and helps test whether a proposed Quran interpretation is lexically possible.

---

## Maqāyīs supports the Root Idea section

Maqāyīs is particularly useful for:

```text
root principle(s)
semantic development
major branches
```

This evidence feeds the top-level explanation of how meanings relate.

It should not be mechanically turned into direct translations of Quran words.

---

## Mufradāt supports Quran-specific distinctions

Mufradāt is especially valuable for:

```text
Quran-focused senses
form distinctions
construction/context distinctions
verse discussions
```

This helps decide which classical meanings are actually relevant to Quran usage.

The five shared/composite articles are segmented before use because assigning an entire mixed article to one root could directly mislead the user.

---

## Quran Foundation word glosses show translation behavior, not lexical truth

The word-by-word English layer helps answer:

```text
How was this Quran word rendered in this particular context?
```

It can help identify useful example verses and recurring contextual renderings.

It must not become the authority for what the Arabic word means.

---

# 5. Why the LLM work is staged

The final user experience requires several different judgments:

```text
What meanings are actually present in Lane?
What root principle does Maqāyīs describe?
What Quran distinctions does Mufradāt make?
Which meanings belong under which Quran form?
How should all of that be explained clearly to a normal reader?
```

Trying to do all of those in one prompt makes it difficult to detect:

- missing meanings
- incorrect form assignment
- overgeneralized root meanings
- source confusion
- unsupported public prose

The staged LLM design therefore exists to protect the user-facing goals:

```text
source completeness
→ correct Quran-form assignment
→ clear public explanation
→ auditable provenance
```

The multiple LLM stages are not multiple independent opinions.

They are separate editorial jobs needed to build one reliable dictionary page.

---

# 6. Product data still needed outside the semantic pipeline

The semantic pipeline deliberately does not embed a full Quran translation into each root record.

Before final application integration, the product still needs separate resources for:

```text
full Arabic verses by verse_key
one or more selectable full-verse translations by translation ID
```

Those resources are **not currently prerequisites for the LLM semantic pilot**. They become required when the new dictionary HTML/product experience is connected to real full-verse display and translation switching.

This boundary prevents translation choice from contaminating or forcing regeneration of the Arabic lexical dictionary.

---

# 7. Target page structure

A successful root page should eventually feel roughly like this:

```text
ROOT: كتب

ROOT IDEA
Short semantic orientation and development
[source chips]

FORMS AND MEANINGS FOUND IN THE QURAN

كَتَبَ
Verb · Form I · 49 occurrences

1. to write or record
2. to prescribe or make obligatory
3. to decree or determine
4. ...

Examples from the Quran
[Arabic verse]
[selected English translation]

كِتَاب
Noun · ...

1. book / written record
2. revealed scripture
3. decree / ordinance
...

OTHER CLASSICAL MEANINGS
[collapsed]

CAUTIONS
[only when needed]

SOURCES
[expandable]
```

The page should help the user move from **translation → Arabic evidence**, not merely from Arabic → another fixed English gloss.

---

# 8. Definition of success

The project succeeds if a user can:

1. click a Quran word,
2. immediately see the relevant Arabic form,
3. understand its main Quranic meanings,
4. compare those meanings with the translation in front of them,
5. inspect Quran examples,
6. see broader classical possibilities when useful,
7. see important uncertainty instead of hidden ambiguity,
8. inspect source evidence if they want to go deeper,
9. change the Quran translation without changing the lexical dictionary,
10. distinguish Quran-attested meanings from broader classical-only meanings,
11. see when evidence is limited or genuinely ambiguous,
12. trust that Quran-attested forms have not silently disappeared during lexical grouping,
13. do all of this without needing to understand QAC IDs, corpus tags, or lexicographic pipeline terminology.

That user experience is the reason the underlying data is being kept form-specific, source-separated, translation-independent, complete, and auditable.
