# Quran Roots — Method, Provenance, Repair History, and Semantic Freeze

**Freeze date:** 2026-08-25  
**Project:** Quran Roots  
**Status:** Semantic dictionary corpus frozen after deterministic freeze audit v2  
**Canonical root count:** 1,642  
**Final numbered artifacts:** 1,642  
**Missing roots:** 0  
**Extra roots:** 0  
**Hard anomalies at freeze:** 0  
**Freeze gate:** PASS

This document supersedes the older operational “handoff” documents as the primary description of **how the Quran Roots semantic dictionary was constructed, repaired, validated, and frozen**.

The older handoff/runbook files remain important historical evidence because they record intermediate states and the discovery of the macOS case-collision incident. They should not be deleted. However, their intermediate root counts are no longer current.

The current publication/reproducibility authority is:

```text
QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_2026-08-25.md
QURAN_ROOTS_REPRODUCIBILITY_FILE_INDEX_2026-08-25.md
QURAN_ROOTS_DOCUMENTATION_INDEX_2026-08-25.md

final/numbered_v7_manifest.json
final/audit/final_freeze_v2/report.json
final/audit/final_freeze_v2/manifest.json
final/audit/final_freeze_v2/anomalies.json
final/audit/final_freeze_v2/outliers.json
```

---

# 1. Purpose and research/product objective

The project builds an auditable Quranic Arabic root dictionary that lets a reader move from:

```text
translated verse
→ actual Arabic word
→ Quran-attested form
→ meanings that form can carry
→ Quran examples
→ broader Classical Arabic meanings
→ source evidence / cautions / ambiguity
```

The central design principle is that **Arabic lexical evidence is independent of a translator’s English choice**.

A Quran translation or word-by-word gloss may help show contextual rendering, but it is not allowed to become the sole lexical authority for a dictionary sense.

The public dictionary is therefore organized around:

- exact Quranic root identity;
- Quran-attested morphological/form groupings;
- form-specific Quranic senses;
- Quran examples tied to stable Quran locations;
- broader Classical meanings kept separate from Quran-attested meanings;
- root-level semantic orientation;
- evidence references and cautions;
- an internal Lane coverage ledger for auditability.

Full Quran translations remain a separate product resource joined later by stable verse/location keys.

---

# 2. Evidence architecture and source roles

The final architecture deliberately assigns different evidentiary jobs to different sources.

| Source | Role in the method | Explicit limitation |
|---|---|---|
| Quranic Arabic Corpus (QAC) | Canonical root identity, morphology, Quran form inventory, occurrence counts, word/segment locations | Not itself a complete Classical lexicon |
| Quran Foundation word-by-word English | Contextual English rendering of Quran words | Never sufficient by itself to create a dictionary sense |
| Lane’s Arabic-English Lexicon | Broad Classical Arabic lexical evidence and lexical branches | Classical breadth does not imply every meaning is Quran-attested |
| Ibn Fāris, *Maqāyīs al-Lugha* | Root principle, semantic orientation, development | Root principle alone cannot establish a direct Quran-form sense |
| al-Rāghib al-Iṣfahānī, *Mufradāt Alfāẓ al-Qurʾān* | Quran-focused lexical distinctions and discussion | Shared/composite rows must not be force-assigned |
| LLM synthesis | Organizes the supplied evidence into the schema | The model is not the lexical authority |
| Deterministic validator/audits | Enforce accounting, identities, references, locations, coverage, and freeze invariants | Warnings are not automatically semantic errors |

## 2.1 External source/access links

### Quranic Arabic Corpus

Canonical local source:

```text
quranic-corpus-morphology-0.4.txt
```

Official download page:

- https://corpus.quran.com/download/

Documentation:

- https://corpus.quran.com/documentation/

The project used **QAC version 0.4**. QAC attribution and source terms must remain attached to publication/distribution.

### Quran Foundation

Local downloaded dataset:

```text
sources/quran-foundation/qf_wbw_en.json
```

Official documentation portal:

- https://api-docs.quran.com/

Content API documentation:

- https://api-docs.quran.com/docs/category/content-apis-4.0.0/

The download used Quran Foundation/Quran.com content access with word-level data. Credentials were kept outside source control. The downloaded corpus should not be assumed freely redistributable merely because it was accessible through the API; publication must follow the applicable Quran Foundation terms/permissions.

### Lane’s Lexicon

Local structured source:

```text
sources/lane/lexicon.sqlite
```

Public database repository corresponding to the local structured Lane source:

- https://github.com/laneslexicon/LexiconDatabase

The repository contains the database used by the Lane’s Lexicon desktop project. Preserve the repository/database provenance and any upstream digitization/edition obligations.

### Maqāyīs and Mufradāt source database

Local aggregate database:

```text
sources/arabic-lexicons/db.sqlite
```

Local provenance/license documentation:

```text
sources/arabic-lexicons/LICENSE.txt
sources/arabic-lexicons/Sources.md
```

Public project repository corresponding to this aggregate lexicon source:

- https://github.com/wizsk/arabic_lexicons

The repository includes Maqāyīs al-Lugha and Mufradāt among its offline lexicons.

**Publication caution:** repository licensing is not automatically proof that every underlying historical edition/digitization may be redistributed in every form. `Sources.md`, `LICENSE.txt`, and upstream provenance should be preserved and reviewed before redistributing large source-derived corpora.

---

# 3. Canonical QAC identity and corpus facts

The QAC morphology file is the identity spine of the project.

Frozen validated corpus facts:

```text
Morphology segment rows:             128,219
Unique Quran word locations:          77,429
Root-bearing segment rows:            49,968
Unique QAC roots:                      1,642
Triliteral roots:                      1,602
Quadriliteral roots:                      40
Surahs:                                   114
```

The canonical root string is the exact case-sensitive QAC/Buckwalter root identifier.

Examples:

```text
DHw != dHw
Slw != slw
```

No casefolding, fuzzy matching, transliteration normalization, or semantic merging is allowed for root identity.

The stable numeric root ID used by the project is:

> the **1-based order of the exact roots in `output/root_synthesis_packets_v3.json`**

The numeric ID is a storage and manifest identity only. It is **not injected into the dictionary artifact schema**.

Final filename format:

```text
<ID>_<exact-root>.json
```

Example:

```text
0427_DHw.json
0428_dHw.json
```

Inside each JSON the canonical identity remains:

```json
{
  "root": "DHw"
}
```

---

# 4. Deterministic QAC preparation

## 4.1 Canonical root list

Script:

```text
extract_unique_quran_roots.py
```

Output:

```text
unique_roots.txt
```

## 4.2 Root/morphology index

Script:

```text
build_quran_root_index.py
```

Output:

```text
quran_roots_index.json
```

The index preserves, per root:

- exact root identity;
- Arabic radicals/root display;
- occurrence/word/surah counts;
- POS counts;
- lemma inventory;
- surface forms;
- verb form/aspect/voice;
- derived nominal information;
- grammatical features;
- word and segment locations.

## 4.3 Quran form inventory

Script:

```text
build_quran_form_inventory_v1.py
```

Primary output:

```text
output/quran_form_inventory_v1.json
```

Validated inventory:

```text
Roots:                        1,642
Root-bearing segments:       49,968
QAC form groups:              4,703
Nominal groups:               3,175
Verb groups:                  1,475
Other root-bearing groups:       53
```

Every root-bearing occurrence belongs to exactly one deterministic QAC form group.

The method distinguishes:

```text
QAC lemma identity
Quran surface form
public/classical citation headword
```

A QAC lemma is not automatically treated as the polished public dictionary headword.

---

# 5. Lane evidence preparation

## 5.1 Root matching

Script:

```text
audit_lane_quran_root_matches_v3.py
```

Result:

```text
QAC roots:          1,642
Lane-matched roots: 1,612
Unmatched:             30
Ambiguous:              0
Match rate:         98.17%
```

Missing Lane material never changes QAC root identity.

## 5.2 Lane extraction

Script:

```text
extract_lane_semantics_v2.py
```

Primary output:

```text
output/lane_quran_semantics_v2.json
```

Validated extraction:

```text
Lane primary attachments: 25,940
XML parse failures:             0
Matched roots with no entries:  0
```

## 5.3 Complete Lane evidence and cross-reference closure

Scripts:

```text
build_lane_complete_sense_packets_v2.py
audit_lane_cross_reference_targets_v1.py
audit_lane_cross_reference_root_local_v1.py
build_lane_complete_root_evidence_v1.py
```

Production complete Lane layer:

```text
output/lane_complete_root_evidence_v1.json
```

Important distinction:

```text
primary Lane evidence
    directly attached to the canonical QAC root

cross-reference context
    followed only because Lane explicitly references it
    contextual only; does not independently create a sense for the root
```

Validated properties included:

```text
Primary attachments preserved:          25,940
Primary Lane source characters:     16,044,722
Maximum cross-reference depth:               4
Unresolved locatable cross-refs:              0
```

## 5.4 Lane source units

The final packet builder exposes deterministic Lane `source_units`.

A source unit is a **reading/accountability boundary**, not a pre-decided dictionary sense.

The model may:

- split one unit into multiple lexical meanings;
- synthesize related units together;
- mark grammar/editorial/pointer material NON_SEMANTIC;
- preserve genuinely uncertain lexical material as AMBIGUOUS.

Every primary Lane source unit must later be accounted for by the internal `lane_unit_coverage` ledger.

---

# 6. Quran Foundation contextual evidence

Download script:

```text
download_quran_foundation_wbw_v4.py
```

Downloaded source:

```text
sources/quran-foundation/qf_wbw_en.json
```

Validated acquisition/join facts:

```text
Mushaf pages:                         604
Unique verses:                      6,236
QF word locations:                 77,430
Canonical QAC word locations:      77,429
QAC locations found in QF:         77,429
Missing QAC words:                      0
Extra QF location:                2:181:14
```

QAC remains canonical; the extra QF location is ignored by the QAC-root join.

Context join:

```text
build_quran_context_glosses_v4.py
```

Primary output:

```text
output/quran_context_glosses_v2.json
```

Root occurrence accounting:

```text
QAC root occurrences:                         49,968
Accounted:                                    49,968
Ordinary whole-word lexical eligible:         48,309
Adjacent repeated-gloss-cluster occurrences:   1,657
Multi-root-segment occurrences quarantined:        2
```

The whole-word contextual English gloss is not allowed to be assigned blindly to individual root-bearing segments in multi-root words.

Core rule:

> Quran Foundation English is contextual rendering evidence only. It cannot establish an Arabic dictionary meaning by itself.

---

# 7. Maqāyīs evidence

Local source:

```text
sources/arabic-lexicons/db.sqlite
```

Root match script:

```text
audit_maqayis_quran_root_matches_v2.py
```

Extraction script:

```text
extract_maqayis_semantics_v2.py
```

Primary evidence output:

```text
output/maqayis_quran_semantics_v2.json
```

Validated matching:

```text
Matched roots:       1,492 / 1,642
Unmatched:             150
Ambiguous:               0
Match rate:          90.86%
```

Deterministic extraction included:

```text
Source rows fetched:                 1,492
Missing source rows:                     0
Heading mismatches:                      0
Roots with principle candidates:     1,359
Principle-candidate clauses:         2,406
```

Maqāyīs is used for:

- root semantic principle(s);
- semantic orientation;
- possible semantic development;
- caution where the source presents multiple principles.

It is not sufficient alone to create a direct Quran-form sense.

---

# 8. Mufradāt evidence

Matching script:

```text
audit_mufradat_quran_matches_v3.py
```

Extraction script:

```text
extract_mufradat_semantics_v1.py
```

Primary output:

```text
output/mufradat_quran_semantics_v1.json
```

Validated matching:

```text
QAC roots with unique Mufradāt match: 1,492 / 1,642
Uniquely assigned source rows:          1,504
Source-row competitions resolved:          36
Genuinely tied/composite rows:               5
```

The five composite rows were deliberately preserved as shared/ambiguous:

```text
row 8     أبا    Abw / Aby
row 606   زاد    zwd / zyd
row 843   صلا    Slw / Sly
row 980   عصا    ESw / ESy
row 1061  غلا    glw / gly
```

They were not force-segmented or force-assigned.

For shared evidence, the synthesis may use only material clearly attributable to the current root; unsupported branches remain unassigned/cautioned.

---

# 9. Deterministic root synthesis packets v3

Builder:

```text
build_root_synthesis_packets_v3.py
```

Canonical production packet file:

```text
output/root_synthesis_packets_v3.json
```

Frozen packet facts:

```text
Root packets:              1,642
Total packet characters: 100,831,624
Maximum packet size:         ~850,303 chars
Large packets:                    15
```

Each packet contains:

- exact canonical root;
- QAC form inventory;
- Quran Foundation representative contextual evidence;
- complete primary Lane evidence;
- Lane cross-reference context;
- Maqāyīs evidence when available;
- Mufradāt unique/shared evidence;
- source registry;
- integrity/accounting metadata.

This packet file is the **canonical evidence bundle supplied to final synthesis and later repair/adjudication**.

---

# 10. Final artifact schema and semantic rules

Production synthesizer:

```text
synthesize_root_dictionary_v11.py
```

The v11 filename contains the production schema/validator/deterministic repair layer. The embedded production synthesis prompt is prompt version **v10**.

The final artifact conceptually contains:

```json
{
  "root": "ktb",
  "arabic": "كتب",
  "root_idea": {},
  "qac_form_accounting": [],
  "quranic_forms": [],
  "other_classical_meanings": [],
  "lane_unit_coverage": [],
  "cautions": [],
  "unassigned_or_ambiguous_evidence": []
}
```

## 10.1 Quran form accounting

Every QAC form group must receive exactly one disposition:

```text
DISPLAY
MERGE
EXCLUDE_WITH_REASON
```

No QAC form group may silently disappear.

## 10.2 Quranic senses

A Quranic sense must have direct lexical support from:

```text
Lane primary evidence
and/or
Mufradāt evidence
```

Quran Foundation may illustrate a sense but cannot create one.

Maqāyīs may inform `root_idea` but cannot create one.

## 10.3 Quran examples

Examples must:

- be real QAC occurrences;
- use valid `verse_key` and `word_location`;
- belong to the relevant root/form;
- reference valid sense IDs on that form.

## 10.4 Broader Classical meanings

Materially distinct Classical meanings are retained under:

```text
other_classical_meanings
```

They are not promoted into Quran-attested senses merely because they occur under the same root.

## 10.5 Lane coverage ledger

Every supplied Lane primary source unit appears exactly once with one of:

```text
REPRESENTED
SUBSUMED
NON_SEMANTIC
AMBIGUOUS
```

`REPRESENTED` and `SUBSUMED` target IDs must resolve to actual Quran sense IDs and/or Classical meaning IDs that genuinely cover the unit’s lexical content.

---

# 11. Production synthesis run

Historical production run label:

```text
luna-high-unit-ledger-v11
```

Authoritative production settings:

```text
model:              gpt-5.6-luna
reasoning:          high
max_output_tokens:  80,000
automatic retries:  none
prompt embedded:    v10
```

Exact imported v11 system-prompt SHA-256 used by the later targeted repairs:

```text
82969fa85bba75435b5ef18c43ada9163402d4edfea86492bfcf5b24003ed6f7
```

The exact production request structure was:

```python
user_prompt = (
    "Synthesize the final dictionary artifact for this root.\n\n"
    "EVIDENCE PACKET JSON:\n"
    + json.dumps(packet, ensure_ascii=False, separators=(",", ":"))
)

response = client.responses.parse(
    model=args.model,
    input=[
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ],
    text_format=RootDictionaryArtifact,
    reasoning={"effort": args.reasoning},
    max_output_tokens=args.max_output_tokens,
)
```

## 11.1 Batch accounting

Canonical roots:

```text
1,642
```

Pre-Batch successful roots skipped from submission:

```text
11
```

Production Batch submissions:

```text
1,631
```

OpenAI Batch result:

```text
1,631 / 1,631 completed
0 Batch-level failures
```

Batch ID:

```text
batch_6a8bc5b224b481908a159a01499e6fa1
```

Immutable raw Batch output:

```text
output/openai-batch-root-dictionary-v1/production-full/batch-001-output.jsonl
```

Other Batch provenance:

```text
output/openai-batch-root-dictionary-v1/production-full/requests-001.jsonl
output/openai-batch-root-dictionary-v1/production-full/manifest.json
output/openai-batch-root-dictionary-v1/production-full/collection_report.json
```

Original collection classification:

```text
accepted clean:              807
accepted with warnings:      455
validation_failed:           256
parse_failed:                  1  (dnr)
skipped_existing_artifact:   112
request_failed:                0
rows:                       1,631
```

The 112 “skipped existing” entries were later proven to be collector/file-system collision effects, **not missing Batch responses**.

Approximate historical Batch cost recorded during production:

```text
~$14.6672459
```

---

# 12. Critical filesystem incident: case-insensitive root collisions

This is one of the most important methodological lessons from the project.

Historical flat files used raw root strings, e.g.:

```text
DHw__attempt-1.json
dHw__attempt-1.json
```

On the default case-insensitive macOS filesystem, those names resolve to the same filesystem namespace.

Two failure modes occurred.

## 12.1 False “existing artifact” skips

A case sibling could satisfy `.exists()` and cause the collector to skip writing a legitimate returned Batch result.

Count:

```text
112 roots
```

## 12.2 Attempt overwrite

If both siblings were written, the later write could replace the earlier file’s contents.

Count:

```text
28 roots
```

A legacy filename could therefore visibly name one root while its internal JSON held another case-distinct root.

## 12.3 Collision accounting

Canonical casefold collision groups:

```text
137 groups
278 roots involved
141 extra identities beyond one physical casefold slot
```

Historical loss classification:

```text
112 collector-skipped identities
 28 overwritten attempt identities
  1 pre-Batch identity: slw
---
141
```

The raw Batch JSONL remained intact and preserved exact custom IDs.

This incident established the permanent storage rule:

```text
<ID>_<exact-root>.json
```

and the permanent identity rule:

```text
numeric ID + exact filename root + exact internal $.root
```

all verified case-sensitively.

---

# 13. Collision recovery and case-safe worksets

Important recovery scripts:

```text
recover_case_collided_batch_roots_v1.py
integrate_collision_recovery_v1.py
recover_all_lost_case_identities_v1.py
build_case_safe_unresolved_workset_v1.py
```

Preservation archive:

```text
final/lost_identity_recovery_v1/
```

All 140 Batch-side collision identities were recovered from the immutable Batch JSONL and preserved using numeric case-safe filenames.

Recovered classification:

```text
140 Batch identities preserved
114 validator-clean
 26 current hard failures
```

The one pre-Batch missing exact identity was:

```text
slw
```

The unresolved workset was frozen under:

```text
final/unresolved_workset_v1/
```

with:

```text
161 possessed unresolved artifacts
135 surviving attempt sources
 26 collision-recovered sources
```

Old flat attempt filenames were retained for historical evidence but no longer trusted for identity.

---

# 14. Special recovery: exact root `slw`

`Slw` and `slw` are distinct canonical QAC roots.

`Slw` had a valid existing artifact.

Exact lowercase:

```text
slw
```

did not have a recoverable historical artifact.

One explicit paid recovery call was run:

```text
run:                slw-single-recovery-v1
model:              gpt-5.6-luna
reasoning:          high
prompt:             v10
input tokens:       16,403
output tokens:       8,808
reasoning tokens:    6,144
estimated cost:     ~$0.0139
validation:         PASSED
stable root ID:      1354
```

Preserved output:

```text
output/root-dictionary-synthesis-attempts/slw-single-recovery-v1/slw__attempt-1.json
output/root_dictionary_artifact_v11__slw-single-recovery-v1__slw.json
```

Final identity:

```text
final/numbered_roots/1354_slw.json
```

---

# 15. Validator-failure repair strategy

After collision recovery and `slw`, the remaining unresolved artifacts were divided into:

```text
157 non-structural roots
4 structural/QAC roots
```

The four structural roots were:

```text
0074 *ll
0262 Ewd
0376 Hyy
1595 ydy
```

Non-structural hard errors were dominated by Lane bookkeeping/reference families.

The project explicitly avoided applying structural heuristics to those four roots.

---

# 16. Targeted non-structural repair history

All targeted repair outputs were staged separately first. No repair runner wrote directly to FINAL until the candidate set was validated.

## 16.1 v2.1 pilot

Script:

```text
targeted_llm_repair_concurrent_v2_1.py
```

Pilot roots:

```text
*qn
Amm
$qq
Asf
E*r
nSb
```

Result:

```text
6 / 6 CLEAN
```

A stable-ID audit verified preservation behavior.

## 16.2 v2.2 full non-structural pass

Script:

```text
targeted_llm_repair_concurrent_v2_2.py
```

Result:

```text
151 calls
134 CLEAN
17 STILL_FAILED
```

## 16.3 v2.3 retry

Script:

```text
targeted_llm_repair_retry_v2_3.py
```

Result:

```text
17 calls
7 CLEAN
10 STILL_FAILED
```

## 16.4 v2.4 surgical patch

Script:

```text
targeted_llm_surgical_patch_v2_4.py
```

The model was not allowed to regenerate the whole artifact.

Permitted patch fields were restricted to:

- complete Lane coverage ledger;
- source-ref updates for existing Quran senses;
- source-ref updates for existing Classical meanings;
- genuinely missing new Classical meanings.

Result initially reported:

```text
4 CLEAN
6 STILL_FAILED
```

Forensics showed five of those six were false preservation-guard failures because the old guard incorrectly treated **new Classical meanings** as forbidden lexical mutation.

The genuine remaining defect was `Ax*`.

## 16.5 Terra adjudication v2.5.1

Script:

```text
terra_final_nonstructural_v2_5_1.py
```

Targets:

```text
Ax*
ErD
bTn
klb
tbE
zkw
```

Terra was used as an independent evidence adjudicator/repairer under the exact imported v11 system methodology.

Result:

```text
6 / 6 CLEAN
remaining hard errors: none
```

Decisions included:

```text
bTn  ACCEPT_EXISTING
tbE  ACCEPT_EXISTING
zkw  ACCEPT_EXISTING
Ax*  REPLACE_WITH_PATCH
klb  REPLACE_WITH_PATCH
ErD  ACCEPT_EXISTING
```

For `ErD`, Terra was explicitly instructed to independently scrutinize the 35 newly proposed Classical branches rather than accept them merely because a previous model produced them.

Non-structural staged result:

```text
157 / 157 solved
```

---

# 17. Integration of all non-structural repairs

Integrator:

```text
integrate_all_nonstructural_final_v1.py
```

Pre-integration numbered FINAL:

```text
1,481
```

Integrated non-structural repairs:

```text
157
```

Result:

```text
1,638 / 1,642 FINAL
4 unresolved structural roots
0 hard errors among FINAL roots
```

New state reports:

```text
final/numbered_v5_manifest.json
final/numbered_v5_report.json
final/numbered_v5_unresolved.json
```

---

# 18. Structural regeneration of the final four roots

Runner:

```text
regenerate_structural_roots_terra_v1.py
```

Method:

- exact imported v11 `SYSTEM_PROMPT`;
- exact original full synthesis user request;
- complete canonical root packet;
- `gpt-5.6-terra`;
- reasoning `high`;
- max output `80,000`;
- current deterministic repair;
- current validator;
- no direct FINAL writes.

Roots and original error families:

```text
0074 *ll
    INVALID_QURAN_EXAMPLE_LOCATION
    OCCURRENCE_COUNT_MISMATCH
    PUBLIC_FORM_MAPPING_MISMATCH
    UNKNOWN_PUBLIC_FORM_QAC_GROUP

0262 Ewd
    INVALID_QURAN_EXAMPLE_LOCATION
    OCCURRENCE_COUNT_MISMATCH
    PUBLIC_FORM_MAPPING_MISMATCH
    QURAN_SENSE_LANE_SUPPORT_NOT_LINKED
    UNKNOWN_PUBLIC_FORM_QAC_GROUP

0376 Hyy
    OCCURRENCE_COUNT_MISMATCH
    QAC_GROUP_IN_MULTIPLE_PUBLIC_FORMS

1595 ydy
    OCCURRENCE_COUNT_MISMATCH
    QAC_GROUP_IN_MULTIPLE_PUBLIC_FORMS
```

Terra result:

```text
4 / 4 CLEAN
remaining hard errors: none
```

Integrator:

```text
integrate_final_four_structural_v1.py
```

Result:

```text
1,642 / 1,642 numbered FINAL
0 unresolved
0 current-validator hard errors
```

State:

```text
final/numbered_v6_manifest.json
```

---

# 19. Freeze audit v1 and newly discovered root-global sense-ID collisions

The first comprehensive freeze audit added invariants beyond the existing validator.

It discovered three root-global duplicate Quran `sense_id` collisions:

```text
0023 $hd
0457 Tlq
1403 syr
```

The old validator had enforced uniqueness within local form scope but not across all public forms in the same root.

Because Lane `target_ids` are root-global, duplicate sense IDs across forms are structurally ambiguous and were treated as genuine freeze blockers.

---

# 20. Deterministic duplicate-sense repair and narrow Terra adjudication

Initial deterministic repair proved:

```text
Tlq  safe
syr  safe
$hd  ambiguous
```

For `$hd`, two different public-form senses sharing the old ID:

```text
shd_shahid_s1
```

both cited Lane entry `39437`.

Two Lane units therefore could not be partitioned by entry number alone:

```text
lane-unit:$hd:39437:g1:main
lane-unit:$hd:39437:g1:sub6
```

A narrow Terra adjudication was used **only for those two Lane rows**.

Terra decision:

```text
lane-unit:$hd:39437:g1:main
    -> shd_shahid

lane-unit:$hd:39437:g1:sub6
    -> shd_shahid
    -> shd_shahid_adj
```

The final installer:

```text
resolve_and_install_duplicate_sense_ids_v2_1.py
```

then performed deterministic ID renaming/reference retargeting for:

```text
$hd
Tlq
syr
```

with:

```text
Lexical rewriting:     0
Duplicate Quran sense IDs after repair: 0
Current validator errors:                0
```

Byte-exact originals were preserved before replacement.

Final manifest:

```text
final/numbered_v7_manifest.json
```

The v7 manifest records:

- the three authorized changed roots;
- old v6 SHA-256;
- new v7 SHA-256;
- preserved original backup path;
- exact ID changes;
- exact Lane reference changes;
- the saved Terra `$hd` adjudication.

---

# 21. Final semantic freeze audit v2

Auditor:

```text
audit_final_numbered_roots_freeze_v2.py
```

Primary report:

```text
final/audit/final_freeze_v2/report.json
```

Final result:

```text
FREEZE GATE: PASS

Canonical packet roots:           1,642
FINAL JSON artifacts:             1,642
Exact internal roots:             1,642
Missing roots:                        0
Extra roots:                          0
Hard anomalies:                       0
Review anomalies:                    34
Structural outlier roots:           285
Warning-bearing roots:              679
Casefold collision groups:          137
Current v7 manifest roots:        1,642
Prior v6 manifest roots:          1,642
Authorized changed roots:             3
Unchanged v6→v7 roots expected:   1,639
```

## 21.1 Identity checks

For all 1,642 roots:

```text
canonical packet root
==
filename exact root
==
JSON $.root
```

using ordinary case-sensitive string equality.

No casefolding, Unicode normalization, or fuzzy mapping is used.

The only root-key location found in final artifacts was:

```text
$.root
```

for all 1,642 files.

## 21.2 Freeze checks

The v2 audit verifies:

- canonical completeness;
- no missing/extra roots;
- safe `<ID>_<exact-root>.json` naming;
- exact numeric ID = packet order;
- exact internal `$.root`;
- no injected top-level `root_id`;
- no duplicate JSON object keys;
- schema validation;
- current deterministic repair stability;
- current validator hard-error freedom;
- local machine-ID uniqueness;
- Lane target resolution;
- casefold-collision preservation;
- v7 SHA-256 agreement;
- v6→v7 provenance continuity;
- 1,639 unchanged roots remain byte-identical to v6;
- the three changed roots match authorized old/new hashes;
- the three preserved original backups match their v6 hashes.

## 21.3 Freeze artifacts

```text
final/audit/final_freeze_v2/report.json
final/audit/final_freeze_v2/report.txt
final/audit/final_freeze_v2/manifest.json
final/audit/final_freeze_v2/root_metrics.csv
final/audit/final_freeze_v2/outliers.json
final/audit/final_freeze_v2/outliers.csv
final/audit/final_freeze_v2/warnings.csv
final/audit/final_freeze_v2/casefold_collision_groups.csv
final/audit/final_freeze_v2/global_id_reuse.json
final/audit/final_freeze_v2/anomalies.json
```

These files, together with `final/numbered_v7_manifest.json`, define the frozen semantic corpus.

---

# 22. Warnings versus hard errors

The final corpus intentionally does **not** require zero warnings.

Warning-bearing roots at freeze:

```text
679
```

Warning code root counts:

```text
LANE_SOURCE_REF_NOT_LINKED_BY_UNIT_LEDGER     496
QF_REPRESENTATIVE_NOT_SUPPLIED                276
QF_GLOSS_MISMATCH                             128
DERIVED_NOMINAL_PARENT_LEXICAL_SUPPORT         31
PUBLIC_DERIVED_NOMINAL_LABEL_TOO_GENERIC        9
PUBLIC_VERB_LABEL_TOO_GENERIC                   2
```

Warnings are retained because eliminating them mechanically can be worse than preserving an honest limitation.

The semantic freeze criterion is:

```text
complete exact-root corpus
+ zero hard validator/freeze anomalies
+ preserved provenance
```

not:

```text
zero warnings
```

---

# 23. Structural outliers and qualitative review

The final freeze audit also computed robust MAD-based structural outliers.

Outliers do not fail the freeze gate by themselves.

Examples of metrics:

- file size;
- QAC accounting row count;
- public form count;
- occurrence totals;
- Quran sense count;
- Quran example count;
- Classical meaning count;
- Lane source-unit count;
- Lane target-link count;
- source reference count;
- definition lengths;
- warning count.

At freeze:

```text
285 roots
```

had one or more review/outlier signals.

This is expected because Quran roots are extremely uneven in frequency and lexical breadth.

## 23.1 Recommended publication QA queue

Before public release, a small human review is recommended without reopening the whole pipeline.

### Highest priority: `ErD`

`0241_ErD.json` is the largest overall semantic outlier and contains:

```text
Classical meanings:       179
Lane units:               265
Lane target links:        228
Source references:        203
```

This includes the earlier **35 newly added Classical meanings** that Terra independently adjudicated.

One exact duplicate Classical definition remains as a review signal:

```text
"an army or great army"
```

under two distinct meaning IDs.

This is not a freeze failure, but it is the most useful human spot-check before publication.

### Duplicate Quran-definition review signals

Eight roots contain distinct Quran sense IDs with exactly repeated English definitions:

```text
Esr
Sdq
fjr
lms
rbE
swA
swm
vlv
```

These may be correct because distinct Arabic forms can share an English definition, but they are worth a quick form-by-form review before publication.

### Global public-form-ID reuse

The freeze audit reports two public-form IDs reused across roots.

This is not root-local corruption, but application code must never assume `public_form_id` is globally unique unless the IDs are namespaced by root.

### Additional useful spot checks

```text
xlf
Eqb
```

are unusually large/complex entries and are reasonable human QA samples.

---

# 24. What is reproducible and what is not

A key publication distinction:

## 24.1 Deterministically reproducible

Given the preserved raw/source datasets and scripts, these layers can be rebuilt deterministically:

- QAC root list/index;
- QAC form inventory;
- Lane root match/extraction;
- Lane cross-reference closure;
- Quran Foundation joins from the preserved downloaded data;
- Maqāyīs matching/extraction;
- Mufradāt matching/extraction;
- root synthesis packets;
- deterministic repairs;
- validators;
- numbered identity mapping;
- freeze audits;
- file hashes/manifests.

## 24.2 Auditable but not guaranteed bit-for-bit reproducible

LLM synthesis/adjudication is **not claimed to be bit-for-bit reproducible**.

Even with:

- the same model name;
- same prompt;
- same evidence packet;
- same output schema;
- same reasoning setting;

a later API execution may produce a different valid textual synthesis.

Therefore publication-grade reproducibility depends on preserving:

```text
raw Batch request JSONL
raw Batch response JSONL
per-root attempt wrappers
model/run metadata
system prompt hash
evidence packets
repair reports
final artifacts
versioned manifests
freeze hashes
```

The preserved outputs are the historical research record.

This distinction should be explicit in any publication: **the evidence preparation and validation are reproducible; the historical LLM editorial transformation is preserved and auditable rather than assumed deterministic.**

---

# 25. Deterministic evidence rebuild order

The production evidence-preparation path is:

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

For publication reproduction from an already preserved source snapshot, it is preferable to retain and hash the downloaded Quran Foundation JSON rather than require a future network/API download to be identical.

---

# 26. Historical production/repair sequence

A concise reconstruction sequence is:

```text
1. Build deterministic evidence layers.
2. Build root_synthesis_packets_v3.json.
3. Run/preserve original production Batch.
4. Collect/preserve per-root responses.
5. Apply deterministic repair + validator.
6. Discover macOS case-insensitive collision incident.
7. Recover all Batch identities from immutable JSONL.
8. Create numbered case-safe FINAL/worksets.
9. Recover exact slw with one dedicated synthesis.
10. Repair 157 non-structural roots through v2.1–v2.5.1.
11. Integrate non-structural roots -> 1638/1642.
12. Full Terra regeneration of *ll, Ewd, Hyy, ydy.
13. Integrate -> 1642/1642.
14. Freeze audit v1 discovers 3 root-global duplicate sense-ID defects.
15. Deterministically fix Tlq/syr and narrow-adjudicate $hd.
16. Install three authorized machine-ID/reference corrections -> v7.
17. Freeze audit v2 -> PASS, 0 hard anomalies.
18. Preserve manual review signals separately from freeze blockers.
```

---

# 27. Files that must never be confused

These have different methodological meanings.

## Canonical evidence packet

```text
output/root_synthesis_packets_v3.json
```

## Immutable original production responses

```text
output/openai-batch-root-dictionary-v1/production-full/batch-001-output.jsonl
```

## Historical per-root collected response wrapper

```text
output/root-dictionary-synthesis-attempts/luna-high-unit-ledger-v11/<ROOT>__attempt-1.json
```

## Historical promoted clean artifact

```text
output/root_dictionary_artifact_v11__luna-high-unit-ledger-v11__<ROOT>.json
```

## Current frozen dictionary corpus

```text
final/numbered_roots/<ID>_<ROOT>.json
```

## Current frozen corpus manifest

```text
final/numbered_v7_manifest.json
```

## Independent final freeze proof

```text
final/audit/final_freeze_v2/
```

The final numbered corpus is the publication/application candidate. The other layers are provenance and rebuild evidence.

---

# 28. Housekeeping and preservation policy after freeze

The semantic corpus is now complete, but destructive cleanup should remain a separate explicit project.

At minimum, preserve permanently:

```text
raw external/source material
source provenance/license files
deterministic preparation scripts
canonical evidence outputs
root_synthesis_packets_v3.json
raw Batch requests/responses
attempt wrappers
collision recovery archives
repair/adjudication outputs
final/numbered_roots/
numbered_v7_manifest.json
final_freeze_v2 audit outputs
method/reproducibility documentation
```

Do not delete or rewrite as part of ordinary cleanup:

```text
visualization/
build_visualization_data.py
```

Older intermediate handoff/runbook documents should be archived, not destroyed, because they document important methodological incidents and intermediate reasoning.

---

# 29. Publication method statement — concise version

A future paper/site may summarize the method approximately as follows:

> Quran Roots uses the Quranic Arabic Corpus v0.4 as the canonical source of Quranic root identity, morphology, form-group structure, occurrence counts, and word locations. Contextual word-level English from Quran Foundation is joined by QAC word location and is used only as contextual rendering evidence. Classical lexical breadth is supplied from Lane’s Lexicon; Ibn Fāris’s Maqāyīs al-Lugha contributes root-level semantic principles; and al-Rāghib al-Iṣfahānī’s Mufradāt contributes Quran-focused lexical discussion. These independently prepared evidence layers are assembled deterministically into one packet per canonical QAC root. A structured LLM synthesis organizes each packet into form-specific Quranic senses, Quran examples, broader Classical meanings, root-level semantic orientation, cautions, and an internal Lane-source-unit coverage ledger. The LLM is treated as an evidence organizer rather than lexical authority. Deterministic validators enforce exact root/form accounting, occurrence counts, valid Quran locations, source references, Lane-unit coverage, stable machine references, and case-sensitive identity. Historical model outputs, raw Batch responses, repair decisions, manifests, and hashes are preserved because LLM generation is auditable but not assumed bit-for-bit reproducible. The final 1,642-root corpus was frozen only after an independent audit confirmed 1,642/1,642 exact roots, no missing or extra roots, preservation of all case-distinct QAC identities, zero hard anomalies, and provenance continuity across authorized repairs.

---

# 30. Current final state

The semantic dataset is frozen at:

```text
final/numbered_roots/
```

Authoritative manifest:

```text
final/numbered_v7_manifest.json
```

Authoritative freeze proof:

```text
final/audit/final_freeze_v2/report.json
final/audit/final_freeze_v2/manifest.json
```

Frozen status:

```text
Canonical roots:        1,642
Final artifacts:        1,642
Missing:                    0
Extra:                      0
Hard anomalies:             0
Freeze gate:             PASS
```

At this point, additional semantic changes should be treated as a **new corpus version**, not silent edits to the frozen v7 corpus.

---

# 31. Documentation supersession rule

Older documents remain historical evidence:

```text
QURAN_ROOTS_PIPELINE_SUMMARY.md
QURAN_ROOTS_USER_EXPERIENCE_GOALS.md
QURAN_ROOTS_PROJECT_STATE_2026-08-24.md
QURAN_ROOTS_CONTINUATION_RUNBOOK.md
QURAN_ROOTS_PROJECT_KNOWLEDGE_INDEX.md
```

For current method/state claims, prefer:

```text
QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_2026-08-25.md
QURAN_ROOTS_REPRODUCIBILITY_FILE_INDEX_2026-08-25.md
QURAN_ROOTS_DOCUMENTATION_INDEX_2026-08-25.md
final/numbered_v7_manifest.json
final/audit/final_freeze_v2/
```

The old documents should not be rewritten to pretend they always described the final state. Their dated intermediate states are part of the audit history.
