# Contributing data corrections

Semantic corrections require more evidence than ordinary code fixes.

## Correction proposal

Provide:

```text
Root ID:
Exact QAC root:
Affected object:
Current value:
Proposed value:
Reason:
Primary source evidence:
Supporting Quran location(s), if relevant:
Source refs:
Does this change IDs? yes/no
Does this change QAC form accounting? yes/no
Does this change occurrence counts? yes/no
```

## Source priority

For root identity, form structure, morphology and Quran occurrence accounting, treat QAC as canonical.

For lexical meaning claims:

- Lane supplies broad Classical lexical evidence;
- Mufradat supplies Quran-focused lexical distinctions;
- Maqayis supports root principle/orientation;
- contextual English glosses do not independently establish dictionary senses.

## Do not

- merge case-distinct QAC roots;
- replace exact source IDs with fuzzy guesses;
- invent source references;
- turn a broad Classical meaning into a Quranic sense without direct evidence;
- silently remove evidence that is difficult to assign;
- rewrite a root solely to match one English Quran translation.

## Merge policy

A maintainer should review the evidence, automated checks, and the semantic impact before merging.

For substantial semantic changes, prefer a new versioned dataset release over silently rewriting an already-published tagged release.
