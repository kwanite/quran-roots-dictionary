# Quran Roots Semantic Data Pipeline — Project Summary

_Last updated: 2026-08-23_

## 1. Project goal

Build a deterministic, auditable Quranic Arabic root dictionary for a Quran application.

The final product must let a user move from a Quran word to its root and independently inspect:

- the Quran-attested forms of that root,
- morphology and occurrence counts,
- distinct Quranic senses,
- representative Quran examples,
- the broader Classical Arabic lexical range,
- root-level semantic orientation/development,
- cautions, ambiguity, and source provenance.

The project deliberately keeps evidence roles separate:

1. **Quranic Arabic Corpus (QAC)** — canonical Quran root, lemma/form identity, morphology, counts, and locations.
2. **Quran Foundation word-by-word English** — contextual English renderings of Quran words.
3. **Lane's Lexicon** — broad Classical Arabic lexical evidence.
4. **Ibn Fāris, Maqāyīs al-Lugha** — root-level semantic principles/orientation.
5. **al-Rāghib al-Iṣfahānī, Mufradāt Alfāẓ al-Qurʾān** — Quran-focused lexical discussion.
6. **One final evidence-grounded LLM synthesis call per root** — organizes the prepared evidence into the public dictionary artifact plus an internal audit ledger.
7. **Deterministic validation** — verifies morphology/form accounting, provenance, Quran locations, and Lane-unit coverage without automatically retrying paid calls.

Core rule:

> A contextual English word-by-word gloss is not the same thing as a dictionary definition.

Quran Foundation English is supporting context only. It must never be the sole lexical authority for creating a dictionary sense.

QAC root IDs remain canonical throughout the pipeline.

The user-facing design goals remain documented separately in:

```text
QURAN_ROOTS_USER_EXPERIENCE_GOALS.md
```

The former staged semantic-extraction architecture has been retired.

---

## 2. Project organization

Use this structure:

```text
SCRIPT / CODE
project root/*.py

RAW / EXTERNAL SOURCE MATERIAL
sources/<source-name>/

GENERATED DATASETS
output/*.json

AUDIT REPORTS
output/*_report*.json
output/*_audit*.json

REVIEW SAMPLES
output/*_sample*.json

PROJECT DOCUMENTATION
project root/*.md

VISUALIZATION
visualization/                 ← DO NOT TOUCH
build_visualization_data.py    ← DO NOT TOUCH
```

All scripts that write generated artifacts should create `output/` with:

```python
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
```

Do not put new generated JSON files in the project root unless they are intentionally small canonical artifacts that predate the `output/` convention.

Never delete, move, rewrite, or incorporate into cleanup:

```text
visualization/
build_visualization_data.py
```

---

## 3. Canonical QAC facts

Canonical morphology source:

```text
quranic-corpus-morphology-0.4.txt
```

Validated facts:

- 128,219 morphology segment rows
- 77,429 unique Quran word locations
- 49,968 root-bearing segment rows
- 1,642 unique QAC roots
- 1,602 triliteral roots
- 40 quadriliteral roots
- 114 surahs

Important implementation details:

- exact TAB parsing
- raw FORM / lemma / ROOT preservation
- initial hamza handled separately from ordinary transliteration
- Form I treated as implicit/default
- indicative mood treated as implicit/default
- trailing numeric lemma discriminators preserved
- multi-STEM Quran words preserved
- QAC word location `(surah:ayah:word)` is canonical for the Quran Foundation join

The sole Quran word with two root-bearing STEM segments is:

```text
20:94:2
يَبْنَؤُمَّ / يَا ابْنَ أُمَّ
"O son of my mother"
```

with roots `bny` and `Amm`.

---

# Current production architecture

The production design is now frozen as:

```text
DETERMINISTIC PREPARATION

QAC morphology + Quran-form inventory
Quran Foundation contextual glosses
Complete Lane evidence + cross-reference context
Maqāyīs evidence
Mufradāt evidence
        ↓
DETERMINISTIC ROOT SYNTHESIS PACKET v3
        ↓
ONE FINAL LUNA/HIGH SYNTHESIS CALL PER ROOT
        ↓
SMALL DETERMINISTIC VALIDATOR
        ↓
FINAL ROOT DICTIONARY ARTIFACT
+ INTERNAL LANE-UNIT COVERAGE LEDGER
```

There is:

- no separate Lane LLM extraction stage,
- no Maqāyīs LLM extraction stage,
- no Mufradāt LLM extraction stage,
- no five-stage semantic pipeline,
- no automatic paid retry,
- no requirement for the LLM to produce archival Lane bookkeeping beyond the compact final coverage ledger.

The LLM is an evidence-grounded synthesizer/organizer, not the lexical authority.

---

# Deterministic source/evidence preparation

## Step 1 — Canonical Quran root list

Script:

```text
extract_unique_quran_roots.py
```

Output:

```text
unique_roots.txt
```

Contains the canonical 1,642 QAC root IDs.

---

## Step 2 — Canonical QAC root/morphology index

Script:

```text
build_quran_root_index.py
```

Output:

```text
quran_roots_index.json
```

Contains, per root:

- root ID / Arabic root / radicals
- occurrence, word, and surah counts
- POS counts
- lemma inventory
- surface forms
- verb forms, aspects, and voice
- derived nominals
- case/state/special features
- word and segment locations

This remains the frozen canonical morphology/root structure.

---

## Step 3 — Canonical Quran-form inventory

Script:

```text
build_quran_form_inventory_v1.py
```

Outputs:

```text
output/quran_form_inventory_v1.json
output/quran_form_inventory_report_v1.json
output/quran_form_inventory_sample_v1.json
```

Validated result:

- 1,642 roots
- 49,968 root-bearing segments
- 4,703 QAC form groups
- 3,175 nominal groups
- 1,475 verb groups
- 53 other root-bearing POS groups
- every root occurrence belongs to exactly one form group
- segment locations are unique

This is a QAC form inventory, not yet a final public-headword inventory.

The inventory explicitly distinguishes:

```text
QAC lemma identity
Quran surface form
public/classical dictionary headword
```

QAC lemmas are therefore internal identities and display candidates, not automatically final public citation forms.

Examples:

```text
Aty
├── أَتَى   Verb · Form I
└── آتَى    Verb · Form IV
```

A public synthesis may normalize an inflected plural or corpus lemma to a singular/classical citation form, but every QAC group must still receive an explicit public-form disposition.

---

## Step 4 — Lane root matching and source extraction

Root-match audit:

```text
audit_lane_quran_root_matches_v3.py
```

Root audit:

```text
lane_root_match_audit_v3.json
```

Validated match result:

- QAC roots: 1,642
- matched Lane roots: 1,612
- unmatched: 30
- ambiguous: 0
- match rate: 98.17%

Missing Lane evidence is allowed and never changes QAC root identity.

Lane source extraction:

```text
extract_lane_semantics_v2.py
```

Outputs:

```text
output/lane_quran_semantics_v2.json
output/lane_extraction_report_v2.json
output/lane_semantics_sample_v2.json
```

Validated extraction:

- 25,940 Lane primary attachments
- 0 Lane XML parse failures
- 0 matched roots with zero extracted Lane entries

The deterministic extraction preserves parsed Lane sense-group structure. That structure is later used to expose smaller semantic reading units without asking an LLM to pre-extract senses.

---

## Step 5 — Complete Lane evidence and cross-reference closure

Relevant deterministic scripts:

```text
build_lane_complete_sense_packets_v2.py
audit_lane_cross_reference_targets_v1.py
audit_lane_cross_reference_root_local_v1.py
build_lane_complete_root_evidence_v1.py
```

Canonical complete Lane outputs:

```text
output/lane_complete_sense_packets_v2.json
output/lane_complete_sense_packets_report_v2.json

output/lane_cross_reference_target_audit_v1.json
output/lane_cross_reference_root_local_audit_v1.json

output/lane_complete_root_evidence_v1.json
output/lane_complete_root_evidence_report_v1.json
output/lane_complete_root_evidence_sample_v1.json
```

The final synthesis pipeline uses:

```text
output/lane_complete_root_evidence_v1.json
```

as its complete Lane evidence layer.

Two Lane roles remain distinct:

```text
primary Lane evidence
    directly attached to the canonical QAC root

cross-reference context
    followed only because Lane explicitly references it
    never independently creates a root sense
```

Validated properties:

- all 25,940 primary Lane attachments preserved
- 16,044,722 characters of primary Lane source text preserved
- explicit node-based cross-references followed transitively
- maximum observed cross-reference depth: 4
- zero unresolved locatable cross-references in the completed closure

---

## Step 6 — Quran Foundation word-by-word contextual English

Download script:

```text
download_quran_foundation_wbw_v4.py
```

Source outputs:

```text
sources/quran-foundation/qf_wbw_en.json
sources/quran-foundation/qf_wbw_download_report.json
sources/quran-foundation/qf_wbw_sample.json
```

Validated source download:

- 604 Mushaf pages
- 6,236 unique verses
- 77,430 QF word locations
- all 77,429 canonical QAC word locations found
- 100% QAC coverage
- 0 missing QAC words
- one extra QF location: `2:181:14`

QAC remains canonical; the extra QF location is ignored by QAC-root joins.

Context-join script:

```text
build_quran_context_glosses_v4.py
```

Outputs:

```text
output/quran_context_glosses_v2.json
output/quran_context_glosses_report_v2.json
output/quran_context_glosses_sample_v2.json
```

Validated result:

- QAC root occurrences: 49,968
- accounted occurrences: 49,968
- missing QF words: 0
- 48,309 ordinary whole-word lexical-frequency-eligible occurrences
- 1,657 occurrences in adjacent repeated-gloss clusters
- 2 multi-root-segment occurrences quarantined

Repeated phrase-level glosses remain preserved separately and are not treated as ordinary root-level lexical-frequency evidence.

Important:

> Quran Foundation English is contextual rendering evidence only. It does not independently establish a dictionary sense.

Full Arabic verses and user-selectable full English translations remain separate UI/context resources and are joined later by `verse_key` / `word_location`.

---

## Step 7 — Maqāyīs root evidence

Source database:

```text
sources/arabic-lexicons/db.sqlite
```

Matching:

```text
audit_maqayis_quran_root_matches_v2.py
```

Outputs:

```text
output/maqayis_root_match_audit_v2.json
output/maqayis_root_match_sample_v2.json
```

Validated matching:

- matched: 1,492 / 1,642
- unmatched: 150
- ambiguous: 0
- match rate: 90.86%

Extraction:

```text
extract_maqayis_semantics_v2.py
```

Outputs:

```text
output/maqayis_quran_semantics_v2.json
output/maqayis_extraction_report_v2.json
output/maqayis_semantics_sample_v2.json
```

Validated extraction:

- 1,492 source rows fetched
- 0 missing source rows
- 0 heading mismatches
- 1,359 roots with deterministic principle candidates
- 2,406 principle-candidate clauses

`principle_candidates` are deterministic source hints, not generated English root meanings.

Maqāyīs is used for:

- root principle(s),
- root-level semantic orientation,
- semantic development,
- cautions about multiple principles/branches.

A Maqāyīs principle must never automatically become a direct Quran-form sense.

---

## Step 8 — Mufradāt Quran-focused evidence

Matching:

```text
audit_mufradat_quran_matches_v3.py
```

Outputs:

```text
output/mufradat_quran_match_audit_v3.json
output/mufradat_quran_match_sample_v3.json
```

Validated result:

- QAC roots with a unique Mufradāt match: 1,492 / 1,642
- uniquely assigned source rows: 1,504
- source-row competitions resolved by evidence ranking: 36
- genuinely tied/composite rows left ambiguous: 5

Extraction:

```text
extract_mufradat_semantics_v1.py
```

Outputs:

```text
output/mufradat_quran_semantics_v1.json
output/mufradat_extraction_report_v1.json
output/mufradat_semantics_sample_v1.json
```

The evidence layer keeps:

```text
unique_entries
shared_ambiguous_entries
```

separate.

The five composite rows remain shared rather than being force-assigned:

```text
row 8     أبا    Abw / Aby
row 606   زاد    zwd / zyd
row 843   صلا    Slw / Sly
row 980   عصا    ESw / ESy
row 1061  غلا    glw / gly
```

There is no separate shared-Mufradāt LLM segmentation stage in the production architecture.

For a shared/composite row:

- the whole row is supplied as ambiguous/contextual evidence,
- the final synthesis may use only passages clearly relevant to the current root,
- unsupported/shared branches must remain unassigned or cautioned,
- the whole shared row must not be treated as uniquely belonging to the current root.

The `Slw` pilot validated this behavior: prayer-related Mufradāt material was used while the fire/burning branch remained explicitly unassigned.

---

# Step 9 — Deterministic root synthesis packets v3

Current packet builder:

```text
build_root_synthesis_packets_v3.py
```

Current pilot outputs:

```text
output/root_synthesis_packets_pilot_v3.json
output/root_synthesis_packets_pilot_report_v3.json
output/root_synthesis_packets_sample_v3.json
```

The builder performs no API calls.

Each root packet contains:

- canonical root identity,
- QAC form inventory,
- Quran Foundation representative contextual gloss evidence,
- complete primary Lane evidence,
- Lane cross-reference context,
- Maqāyīs evidence when available,
- Mufradāt unique/shared evidence,
- a source registry,
- deterministic integrity metadata.

## Lane primary source units

Primary Lane entries are exposed through deterministic `source_units` derived from Lane's already-parsed `sense_groups`.

A source unit is:

> a semantic reading boundary, not a pre-decided dictionary sense.

The final model may:

- split one unit into multiple lexical meanings,
- combine related units,
- classify pointer/grammar/editorial/example-only units as non-semantic,
- preserve uncertain lexical material as ambiguous.

Unit IDs use Lane's own sub-number when available, so `unit_id`, `lane_marker`, and `sub_number` do not present competing numbering systems.

Cross-reference targets remain context-only prose and do not create unit-level sense obligations for the current root.

Representative v3 pilot packet sizes:

| Root | Packet chars | Lane primary units |
|---|---:|---:|
| `rHm` | ~238k | 47 |
| `ktb` | ~236k | 61 |
| `Aty` | ~471k | 58 |
| `Hqq` | ~266k | 107 |
| `Slw` | ~94k | 23 |

---

# Step 10 — Final root dictionary synthesis v11

Current production synthesizer:

```text
synthesize_root_dictionary_v11.py
```

Production settings:

```text
model:              gpt-5.6-luna
reasoning:          high
max_output_tokens:  40,000
API calls:           exactly one per requested root
automatic retry:     none
```

The script has a dry-run mode by default.

A paid call requires:

```text
--confirm-api
```

The 40,000-token ceiling is intentional. High-reasoning synthesis plus a large Lane coverage ledger can exceed the former 20,000-token combined reasoning/output allowance.

If local structured-output parsing fails after a paid call, the script attempts to preserve recovered raw model text in the attempt record rather than silently losing the paid response.

## Public artifact structure

Conceptually:

```json
{
  "root": "ktb",
  "arabic": "كتب",
  "root_idea": {
    "summary": "...",
    "development": "...",
    "source_refs": []
  },
  "qac_form_accounting": [],
  "quranic_forms": [
    {
      "public_form_id": "...",
      "form_group_ids": [],
      "headword_arabic": "...",
      "public_pos_label": "...",
      "verb_form": "...",
      "occurrence_count": 0,
      "senses": [],
      "quran_examples": []
    }
  ],
  "other_classical_meanings": [],
  "lane_unit_coverage": [],
  "cautions": [],
  "unassigned_or_ambiguous_evidence": []
}
```

Public-facing definitions remain source-neutral. Source attribution remains in structured `source_refs`.

---

## Quran form accounting

Every QAC form group must receive exactly one disposition:

```text
DISPLAY
MERGE
EXCLUDE_WITH_REASON
```

Rules:

- `DISPLAY` must target the public form that contains the QAC group.
- `MERGE` must name the public target and give a reason.
- `EXCLUDE_WITH_REASON` requires an explicit reason.
- no Quran-attested form group may silently disappear.

Public headwords are normalized lexically rather than blindly copied from QAC.

Examples:

- inflected plural active participle → singular citation form when supported,
- QAC corpus lemma → classical/public citation form when the evidence justifies normalization.

---

## Quranic senses

A Quranic dictionary sense must have direct lexical support from Lane and/or Mufradāt.

Quran Foundation contextual English:

- can illustrate a supported sense,
- can help select examples,
- can show contextual translation variation,
- cannot create a sense by itself.

Maqāyīs:

- supports root-level principles/development,
- cannot by itself create a direct Quranic form sense.

Classical-only specializations must remain under `other_classical_meanings` unless Quran-focused evidence actually establishes the specialization in Quranic usage.

An illustrative Lane example must not be turned into a universal restriction on gender, animacy, class, number, or social status unless the lexical evidence explicitly states that restriction.

---

## Quran examples

Examples must:

- resolve to genuine QAC occurrences,
- have a matching `verse_key`,
- belong to the displayed root/form,
- point only to valid sense IDs,
- semantically demonstrate the assigned sense.

The stored artifact uses stable Quran pointers:

```text
verse_key
word_location
```

Full Arabic verse text and selectable full translations remain separate application resources.

---

## Other Classical meanings

Lane primary evidence is reviewed comprehensively.

Materially independent Classical meanings must be:

- represented as their own Classical meaning,
- genuinely subsumed under an explicit target,
- or retained as ambiguous/cautioned evidence.

Rare, dialectal, tentative, bracketed, or authority-attributed lexical statements are not discarded merely because they are unusual.

Pointer-only, grammatical, pronunciation, orthographic, editorial, or example-only material need not become dictionary meanings.

Lexical identity must be respected: a meaning stated for one headword or derived form must not be moved to another merely because they are semantically related.

---

# Internal Lane-unit coverage ledger

`lane_unit_coverage` is audit metadata, not intended for the public UI.

Every supplied Lane primary source unit must appear exactly once with one status:

```text
REPRESENTED
SUBSUMED
NON_SEMANTIC
AMBIGUOUS
```

For `REPRESENTED` / `SUBSUMED`:

- `target_ids` must name actual Quran sense IDs and/or Classical meaning IDs,
- the target must actually state the unit's lexical content,
- semantic resemblance alone is not enough.

When one Lane unit contains several materially distinct branches and several are represented, the ledger must list all represented targets.

For `NON_SEMANTIC`:

- the unit must genuinely add no lexical meaning.

For `AMBIGUOUS`:

- the uncertainty must also remain visible in `unassigned_or_ambiguous_evidence`.

This ledger is the anti-loss mechanism that replaced the former standalone Lane LLM sense-inventory stage.

---

# Deterministic validation

The validator performs structural and provenance checks after the one paid synthesis call.

Important hard checks include:

- root identity
- complete QAC form-group accounting
- no duplicate/missing public-form mappings
- public occurrence counts equal QAC counts
- no duplicate sense IDs
- genuine source refs only
- lexical senses must have direct Lane/Mufradāt support
- genuine Quran locations
- verse-key/location consistency
- Quran example sense IDs exist
- root-idea and Classical source refs exist
- every Lane primary source unit is accounted for exactly once
- ledger targets exist
- ambiguous Lane material is not silently dropped

Warnings may include:

- Quran Foundation representative/gloss differences that can be deterministically rejoined later,
- corroborative Lane citations not directly linked by the unit ledger,
- transparent derived-nominal parent-verb support.

A transparent QAC-derived verbal noun / active participle / passive participle may inherit its parent-verb lexical branch when the entire public form is deterministically identified as that derivative. Missing a separate Lane derivative entry is therefore a warning, not automatically a hard failure.

No validation failure triggers an automatic paid retry.

---

# Historical Lane citation caution

Lane uses historical Quran citation conventions, including Roman numerals.

A transcription such as:

```text
[1. 18]
```

must not automatically be interpreted as modern Quran `1:18`.

When Lane quotes an Arabic Quran expression:

- treat the quoted Arabic as Quran-focused lexical evidence,
- assign a modern `verse_key` only when independently supported by QAC,
- otherwise preserve the interpretation without inventing a modern location.

This rule was added after the `Hqq` pilot exposed a Roman-numeral citation being misread as an Arabic numeral.

---

# Pilot validation and architecture freeze

The representative pilot roots were:

```text
rHm
ktb
Aty
Hqq
Slw
```

The iterations established the following:

- complete Lane source units materially improved preservation of uncommon Classical meanings,
- the internal Lane-unit ledger exposed silent omissions and bad subsumption decisions,
- source-native Lane sub-number IDs removed unit-number ambiguity,
- high reasoning substantially improved semantic accounting,
- a 40,000-token output ceiling is required for dense roots,
- shared Mufradāt evidence can be handled safely in the one final synthesis call,
- deterministic validation is effective without automatic paid retries.

`Hqq` demonstrated dense lexical coverage with 107 Lane units.

`Slw` demonstrated the opposite evidence profile:

- only 23 Lane units,
- no matched Maqāyīs entry,
- a shared/composite Mufradāt row,
- separate prayer, blessing, place-of-worship, racing, anatomical, and other Classical branches.

The `Slw` v11 run passed:

```text
0 hard errors
2 warnings
```

The synthesis architecture is therefore frozen at:

```text
PACKETS:     build_root_synthesis_packets_v3.py
SYNTHESIS:   synthesize_root_dictionary_v11.py
MODEL:       gpt-5.6-luna
REASONING:   high
MAX OUTPUT:  40,000
```

Do not create another prompt version merely to eliminate harmless audit warnings.

---

# Retained frozen baselines

The following older combined datasets may remain as historical rollback/reference artifacts but are **not part of the production synthesis path**:

```text
output/quran_root_semantics_combined_v1.json
output/quran_root_semantics_combined_v2.json
output/quran_root_semantics_combined_report_v2.json
output/quran_root_semantics_combined_sample_v2.json
```

Their builders may remain for reproducibility:

```text
build_combined_quran_semantics.py
build_combined_quran_semantics_v2.py
```

Do not feed these frozen combined files into the production v11 synthesizer.

---

# Current scripts to keep

```text
extract_unique_quran_roots.py
build_quran_root_index.py
build_quran_form_inventory_v1.py

audit_lane_quran_root_matches_v3.py
inspect_lane_sqlite.py
extract_lane_semantics_v2.py
build_lane_complete_sense_packets_v2.py
audit_lane_cross_reference_targets_v1.py
audit_lane_cross_reference_root_local_v1.py
build_lane_complete_root_evidence_v1.py

download_quran_foundation_wbw_v4.py
build_quran_context_glosses_v4.py

inspect_arabic_lexicons_sqlite.py
audit_maqayis_quran_root_matches_v2.py
extract_maqayis_semantics_v2.py
audit_mufradat_quran_matches_v3.py
extract_mufradat_semantics_v1.py

build_combined_quran_semantics.py
build_combined_quran_semantics_v2.py

build_root_synthesis_packets_v3.py
synthesize_root_dictionary_v11.py
```

Visualization remains separate and untouched:

```text
build_visualization_data.py
visualization/
```

---

# Obsolete/replaced files

The following logic has been superseded by the frozen architecture and should not be part of the active tree:

```text
extract_lane_sense_inventory_v1.py
build_lane_sense_extraction_packets_v3.py
build_mufradat_shared_segmentation_packets_v1.py

build_root_synthesis_packets_v1.py
build_root_synthesis_packets_v2.py

synthesize_root_dictionary_v1.py
synthesize_root_dictionary_v1_PY39.py
synthesize_root_dictionary_v2.py
...
synthesize_root_dictionary_v10.py
```

Old Lane-inventory attempts/checkpoints, old packet versions, and superseded pilot artifacts may also be removed or archived.

Git history is the appropriate place to recover retired experimental logic if comparison is ever needed.

---

# Canonical/current outputs to keep

Project root:

```text
unique_roots.txt
quran_roots_index.json
lane_root_match_audit_v3.json
quranic-corpus-morphology-0.4.txt
```

QAC form inventory:

```text
output/quran_form_inventory_v1.json
output/quran_form_inventory_report_v1.json
output/quran_form_inventory_sample_v1.json
```

Lane:

```text
output/lane_quran_semantics_v2.json
output/lane_extraction_report_v2.json
output/lane_semantics_sample_v2.json

output/lane_complete_sense_packets_v2.json
output/lane_complete_sense_packets_report_v2.json

output/lane_cross_reference_target_audit_v1.json
output/lane_cross_reference_root_local_audit_v1.json

output/lane_complete_root_evidence_v1.json
output/lane_complete_root_evidence_report_v1.json
output/lane_complete_root_evidence_sample_v1.json
```

Quran Foundation:

```text
sources/quran-foundation/qf_wbw_en.json
sources/quran-foundation/qf_wbw_download_report.json
sources/quran-foundation/qf_wbw_sample.json
```

Quran context:

```text
output/quran_context_glosses_v2.json
output/quran_context_glosses_report_v2.json
output/quran_context_glosses_sample_v2.json
```

Maqāyīs:

```text
output/maqayis_root_match_audit_v2.json
output/maqayis_root_match_sample_v2.json
output/maqayis_quran_semantics_v2.json
output/maqayis_extraction_report_v2.json
output/maqayis_semantics_sample_v2.json
```

Mufradāt:

```text
output/mufradat_quran_match_audit_v3.json
output/mufradat_quran_match_sample_v3.json
output/mufradat_quran_semantics_v1.json
output/mufradat_extraction_report_v1.json
output/mufradat_semantics_sample_v1.json
```

Current synthesis packet pilot/regression artifacts:

```text
output/root_synthesis_packets_pilot_v3.json
output/root_synthesis_packets_pilot_report_v3.json
output/root_synthesis_packets_sample_v3.json
```

Accepted pilot synthesis artifacts may be retained for regression review:

```text
output/root_dictionary_artifact_v10__luna-high-unit-ledger-v10__Hqq.json
output/root_dictionary_artifact_report_v10__luna-high-unit-ledger-v10__Hqq.json

output/root_dictionary_artifact_v11__luna-high-unit-ledger-v11__Slw.json
output/root_dictionary_artifact_report_v11__luna-high-unit-ledger-v11__Slw.json
```

Raw source material:

```text
sources/lane/lexicon.sqlite

sources/arabic-lexicons/db.sqlite
sources/arabic-lexicons/LICENSE.txt
sources/arabic-lexicons/Sources.md
```

---

# Deterministic rebuild order

Current source/evidence rebuild path:

```bash
/Library/Developer/CommandLineTools/usr/bin/python3 extract_unique_quran_roots.py
/Library/Developer/CommandLineTools/usr/bin/python3 build_quran_root_index.py
/Library/Developer/CommandLineTools/usr/bin/python3 build_quran_form_inventory_v1.py

/Library/Developer/CommandLineTools/usr/bin/python3 audit_lane_quran_root_matches_v3.py
/Library/Developer/CommandLineTools/usr/bin/python3 extract_lane_semantics_v2.py
/Library/Developer/CommandLineTools/usr/bin/python3 build_lane_complete_sense_packets_v2.py
/Library/Developer/CommandLineTools/usr/bin/python3 audit_lane_cross_reference_targets_v1.py
/Library/Developer/CommandLineTools/usr/bin/python3 audit_lane_cross_reference_root_local_v1.py
/Library/Developer/CommandLineTools/usr/bin/python3 build_lane_complete_root_evidence_v1.py

/Library/Developer/CommandLineTools/usr/bin/python3 download_quran_foundation_wbw_v4.py
/Library/Developer/CommandLineTools/usr/bin/python3 build_quran_context_glosses_v4.py

/Library/Developer/CommandLineTools/usr/bin/python3 audit_maqayis_quran_root_matches_v2.py
/Library/Developer/CommandLineTools/usr/bin/python3 extract_maqayis_semantics_v2.py

/Library/Developer/CommandLineTools/usr/bin/python3 audit_mufradat_quran_matches_v3.py
/Library/Developer/CommandLineTools/usr/bin/python3 extract_mufradat_semantics_v1.py

/Library/Developer/CommandLineTools/usr/bin/python3 build_root_synthesis_packets_v3.py
```

The two frozen combined builders are optional historical rebuilds and are not required by the production v11 path.

Do not run retired Lane sense-inventory extraction or shared-Mufradāt segmentation stages.

---

# Source/provenance notes

## Quranic Arabic Corpus

Canonical morphology:

```text
quranic-corpus-morphology-0.4.txt
```

Preserve QAC v0.4 attribution. Do not modify the source file in place.

## Lane's Lexicon

Local structured source:

```text
sources/lane/lexicon.sqlite
```

Preserve Lane provenance/version metadata.

## Quran Foundation

Downloaded source:

```text
sources/quran-foundation/qf_wbw_en.json
```

Keep credentials/tokens outside source control. Treat the downloaded corpus as authorized source material, not automatically redistributable standalone data.

## Arabic Lexicons aggregate database

Source:

```text
sources/arabic-lexicons/db.sqlite
```

Documentation:

```text
sources/arabic-lexicons/LICENSE.txt
sources/arabic-lexicons/Sources.md
```

Preserve source provenance and review redistribution rights before public release of source-derived corpora.

---

# Git / repository policy

Normally do not commit:

```gitignore
.env
.env.*
!.env.example

.DS_Store
__pycache__/
*.py[cod]
.venv/
venv/

*.sqlite-wal
*.sqlite-shm
*.sqlite-journal

sources/lane/lexicon.sqlite

sources/arabic-lexicons/db.sqlite
sources/arabic-lexicons/db.sqlite.zip

sources/quran-foundation/cache/
sources/quran-foundation/page-cache-v4/
sources/quran-foundation/qf_wbw_en.json
sources/quran-foundation/qf_wbw_sample.json
sources/quran-foundation/qf_wbw_download_report.json

output/*_sample*.json

output/lane_quran_semantics_v2.json
output/quran_context_glosses_v2.json
output/maqayis_quran_semantics_v2.json
output/mufradat_quran_semantics_v1.json

output/lane_complete_sense_packets_v2.json
output/lane_complete_root_evidence_v1.json

output/quran_form_inventory_v1.json

output/root_synthesis_packets_v3.json
output/root_synthesis_packets_pilot_v3.json

output/root-dictionary-synthesis-attempts/
```

Do not broadly ignore all of `output/`; small audit/report JSON files can remain trackable when useful.

Never modify or ignore as part of pipeline cleanup:

```text
visualization/
build_visualization_data.py
```

---

# Immediate next step

The semantic architecture is frozen.

The next development task is a **production batch runner** around:

```text
synthesize_root_dictionary_v11.py
```

The runner should provide:

- controlled root selection,
- full-corpus / subset modes,
- resume behavior,
- skip already accepted artifacts,
- no automatic retry of paid failures,
- per-root failure isolation,
- parse-failure preservation,
- cost/token accounting,
- deterministic validation status capture,
- final corpus batch report,
- easy restart after interruption.

Before batch execution:

1. clean obsolete experimental files,
2. replace this summary with the current version,
3. build/verify the full v3 root synthesis packet dataset,
4. implement and dry-run the batch runner,
5. begin paid corpus synthesis only after the batch runner's skip/resume behavior is verified.

The production semantic design itself should not be revised merely to remove harmless audit warnings.
