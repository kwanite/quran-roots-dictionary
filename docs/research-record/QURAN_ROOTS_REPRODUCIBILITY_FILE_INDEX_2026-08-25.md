# Quran Roots — Reproducibility and Key File Index

**Date:** 2026-08-25  
**Purpose:** Identify the files required to understand, reproduce, audit, or reconstruct the Quran Roots semantic dictionary.

This is the practical companion to:

```text
QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_2026-08-25.md
```

The guiding preservation rule is:

> Preserve the source snapshot, deterministic evidence layers, immutable model responses, repair provenance, and final hashes. Do not rely on chat history or terminal scrollback as the only record.

---

# 1. Highest-priority freeze files

These are the first files to inspect when establishing current truth.

```text
final/numbered_v7_manifest.json
final/audit/final_freeze_v2/report.json
final/audit/final_freeze_v2/manifest.json
final/audit/final_freeze_v2/anomalies.json
final/audit/final_freeze_v2/outliers.json
final/audit/final_freeze_v2/root_metrics.csv
final/audit/final_freeze_v2/warnings.csv
final/audit/final_freeze_v2/casefold_collision_groups.csv
final/audit/final_freeze_v2/global_id_reuse.json
```

Current frozen corpus:

```text
final/numbered_roots/
```

Expected:

```text
1,642 JSON files
<ID>_<exact-root>.json
```

---

# 2. Primary source data — must preserve

## QAC

```text
quranic-corpus-morphology-0.4.txt
```

External:

```text
https://corpus.quran.com/download/
https://corpus.quran.com/documentation/
```

## Lane

```text
sources/lane/lexicon.sqlite
```

External:

```text
https://github.com/laneslexicon/LexiconDatabase
```

## Quran Foundation

```text
sources/quran-foundation/qf_wbw_en.json
sources/quran-foundation/qf_wbw_download_report.json
sources/quran-foundation/qf_wbw_sample.json
```

External documentation:

```text
https://api-docs.quran.com/
https://api-docs.quran.com/docs/category/content-apis-4.0.0/
```

## Maqāyīs + Mufradāt aggregate source

```text
sources/arabic-lexicons/db.sqlite
sources/arabic-lexicons/LICENSE.txt
sources/arabic-lexicons/Sources.md
```

External project repository:

```text
https://github.com/wizsk/arabic_lexicons
```

`Sources.md` and upstream source notes are publication-critical.

---

# 3. Canonical deterministic QAC outputs

```text
unique_roots.txt
quran_roots_index.json

output/quran_form_inventory_v1.json
output/quran_form_inventory_report_v1.json
output/quran_form_inventory_sample_v1.json
```

Scripts:

```text
extract_unique_quran_roots.py
build_quran_root_index.py
build_quran_form_inventory_v1.py
```

---

# 4. Lane deterministic outputs

Root match:

```text
lane_root_match_audit_v3.json
audit_lane_quran_root_matches_v3.py
```

Extraction:

```text
output/lane_quran_semantics_v2.json
output/lane_extraction_report_v2.json
output/lane_semantics_sample_v2.json

extract_lane_semantics_v2.py
```

Complete Lane coverage:

```text
output/lane_complete_sense_packets_v2.json
output/lane_complete_sense_packets_report_v2.json

output/lane_cross_reference_target_audit_v1.json
output/lane_cross_reference_root_local_audit_v1.json

output/lane_complete_root_evidence_v1.json
output/lane_complete_root_evidence_report_v1.json
output/lane_complete_root_evidence_sample_v1.json
```

Scripts:

```text
build_lane_complete_sense_packets_v2.py
audit_lane_cross_reference_targets_v1.py
audit_lane_cross_reference_root_local_v1.py
build_lane_complete_root_evidence_v1.py
```

---

# 5. Quran Foundation/Quran context outputs

```text
sources/quran-foundation/qf_wbw_en.json

output/quran_context_glosses_v2.json
output/quran_context_glosses_report_v2.json
output/quran_context_glosses_sample_v2.json
```

Scripts:

```text
download_quran_foundation_wbw_v4.py
build_quran_context_glosses_v4.py
```

For strict historical reproduction, preserve the downloaded `qf_wbw_en.json` rather than assuming a future API call will return a byte-identical dataset.

---

# 6. Maqāyīs outputs

```text
output/maqayis_root_match_audit_v2.json
output/maqayis_root_match_sample_v2.json
output/maqayis_quran_semantics_v2.json
output/maqayis_extraction_report_v2.json
output/maqayis_semantics_sample_v2.json
```

Scripts:

```text
audit_maqayis_quran_root_matches_v2.py
extract_maqayis_semantics_v2.py
```

---

# 7. Mufradāt outputs

```text
output/mufradat_quran_match_audit_v3.json
output/mufradat_quran_match_sample_v3.json
output/mufradat_quran_semantics_v1.json
output/mufradat_extraction_report_v1.json
output/mufradat_semantics_sample_v1.json
```

Scripts:

```text
audit_mufradat_quran_matches_v3.py
extract_mufradat_semantics_v1.py
```

Historical shared-segmentation experiments, if retained, are not part of the final production architecture.

---

# 8. Canonical synthesis packet

Critical:

```text
output/root_synthesis_packets_v3.json
```

Builder:

```text
build_root_synthesis_packets_v3.py
```

This file freezes the evidence supplied to root synthesis and repair adjudications.

Do not delete.

---

# 9. Production synthesizer / validator

Critical:

```text
synthesize_root_dictionary_v11.py
```

The file includes:

- final Pydantic artifact schema;
- production system prompt;
- deterministic bookkeeping repairs;
- validator.

Historical system-prompt SHA-256 used in the repair/finalization phase:

```text
82969fa85bba75435b5ef18c43ada9163402d4edfea86492bfcf5b24003ed6f7
```

This should be preserved in publication metadata.

---

# 10. Original production Batch — immutable provenance

Directory:

```text
output/openai-batch-root-dictionary-v1/production-full/
```

Critical files:

```text
requests-001.jsonl
batch-001-output.jsonl
manifest.json
collection_report.json
```

The raw Batch JSONL is the authoritative forensic source for exact returned Batch identities.

Do not delete, reformat, or replace it with per-root files.

---

# 11. Historical per-root production results

Attempt wrappers:

```text
output/root-dictionary-synthesis-attempts/luna-high-unit-ledger-v11/
```

Historical promoted artifacts:

```text
output/root_dictionary_artifact_v11__luna-high-unit-ledger-v11__<ROOT>.json
```

Important warning:

> The old flat filename namespace is collision-prone on case-insensitive macOS. Do not trust legacy filename casing as identity proof.

Use exact internal root identity and numbered case-safe stores.

---

# 12. Collision incident and recovery provenance

Key scripts:

```text
recover_case_collided_batch_roots_v1.py
integrate_collision_recovery_v1.py
recover_all_lost_case_identities_v1.py
build_case_safe_unresolved_workset_v1.py
```

Key directories:

```text
final/collision_recovery/
final/lost_identity_recovery_v1/
final/unresolved_workset_v1/
```

Especially preserve:

```text
final/lost_identity_recovery_v1/raw_batch_rows/
final/lost_identity_recovery_v1/original_artifacts/
final/lost_identity_recovery_v1/current_repaired_artifacts/
final/lost_identity_recovery_v1/validation/
final/lost_identity_recovery_v1/recovery_manifest.json
final/lost_identity_recovery_v1/recovery_report.json
```

These prove that case-distinct roots were recovered from exact Batch IDs rather than fuzzy/casefold inference.

---

# 13. `slw` recovery provenance

```text
output/root-dictionary-synthesis-attempts/slw-single-recovery-v1/slw__attempt-1.json
output/root_dictionary_artifact_v11__slw-single-recovery-v1__slw.json
output/root_dictionary_artifact_report_v11__slw-single-recovery-v1__slw.json
integrate_slw_single_recovery_v1.py
```

Final:

```text
final/numbered_roots/1354_slw.json
```

---

# 14. Targeted non-structural repair files

## Pilot v2.1

```text
targeted_llm_repair_concurrent_v2_1.py
final/targeted_llm_repair_v2_1/
```

## Main pass v2.2

```text
targeted_llm_repair_concurrent_v2_2.py
final/targeted_llm_repair_v2_2/
```

## Retry v2.3

```text
targeted_llm_repair_retry_v2_3.py
final/targeted_llm_repair_v2_3/
```

## Surgical v2.4

```text
targeted_llm_surgical_patch_v2_4.py
final/targeted_llm_repair_v2_4/
```

## Terra adjudication v2.5.1

```text
terra_final_nonstructural_v2_5_1.py
final/targeted_llm_repair_v2_5_1_terra/
```

These directories preserve attempts, decisions/patches, clean candidates, validations, and reports.

---

# 15. Non-structural final integration

```text
integrate_all_nonstructural_final_v1.py
```

Reports/state:

```text
final/numbered_v5_manifest.json
final/numbered_v5_report.json
final/numbered_v5_unresolved.json
```

This checkpoint proves 1,638/1,642 after all 157 non-structural repairs.

---

# 16. Final structural four

Regeneration:

```text
regenerate_structural_roots_terra_v1.py
final/structural_regeneration_terra_v1/
```

Targets:

```text
0074 *ll
0262 Ewd
0376 Hyy
1595 ydy
```

Integrator:

```text
integrate_final_four_structural_v1.py
```

Checkpoint:

```text
final/numbered_v6_manifest.json
final/numbered_v6_report.json
final/numbered_v6_unresolved.json
```

---

# 17. Duplicate Quran sense-ID final correction

Historical first diagnostic/fix:

```text
repair_duplicate_quran_sense_ids_v1.py
```

Narrow Terra + deterministic final resolver:

```text
resolve_and_install_duplicate_sense_ids_v2_1.py
```

Repair directory:

```text
final/duplicate_sense_id_fix_v2_1/
```

Preserved originals:

```text
final/duplicate_sense_id_fix_v2_1/originals/
```

Changed roots:

```text
0023 $hd
0457 Tlq
1403 syr
```

Authoritative post-fix manifest:

```text
final/numbered_v7_manifest.json
```

---

# 18. Final freeze audit

Script:

```text
audit_final_numbered_roots_freeze_v2.py
```

Outputs:

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

This is the authoritative independent freeze proof.

---

# 19. Current frozen corpus

Critical directory:

```text
final/numbered_roots/
```

Expected count:

```text
1,642
```

Filename identity:

```text
<ID>_<exact-root>.json
```

Current manifest:

```text
final/numbered_v7_manifest.json
```

Any future semantic edit should produce a new manifest/corpus version rather than silently modifying v7.

---

# 20. Documentation files

New publication/reproducibility authority:

```text
QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_2026-08-25.md
QURAN_ROOTS_REPRODUCIBILITY_FILE_INDEX_2026-08-25.md
QURAN_ROOTS_DOCUMENTATION_INDEX_2026-08-25.md
```

Historical documents to retain:

```text
QURAN_ROOTS_PIPELINE_SUMMARY.md
QURAN_ROOTS_USER_EXPERIENCE_GOALS.md
QURAN_ROOTS_PROJECT_STATE_2026-08-24.md
QURAN_ROOTS_CONTINUATION_RUNBOOK.md
QURAN_ROOTS_PROJECT_KNOWLEDGE_INDEX.md
```

Older handoff counts are historical, not current.

---

# 21. Files that must not be touched by semantic cleanup

```text
visualization/
build_visualization_data.py
```

These are outside the semantic pipeline cleanup scope.

---

# 22. Minimal disaster-recovery set

If storage must be reduced to the smallest defensible archive capable of supporting reconstruction/audit, preserve at least:

```text
quranic-corpus-morphology-0.4.txt

sources/lane/lexicon.sqlite
sources/arabic-lexicons/db.sqlite
sources/arabic-lexicons/LICENSE.txt
sources/arabic-lexicons/Sources.md
sources/quran-foundation/qf_wbw_en.json
sources/quran-foundation/qf_wbw_download_report.json

all deterministic source-preparation scripts

output/root_synthesis_packets_v3.json

synthesize_root_dictionary_v11.py

output/openai-batch-root-dictionary-v1/production-full/
output/root-dictionary-synthesis-attempts/

final/lost_identity_recovery_v1/
final/unresolved_workset_v1/
final/targeted_llm_repair_v2_1/
final/targeted_llm_repair_v2_2/
final/targeted_llm_repair_v2_3/
final/targeted_llm_repair_v2_4/
final/targeted_llm_repair_v2_5_1_terra/
final/structural_regeneration_terra_v1/
final/duplicate_sense_id_fix_v2_1/

final/numbered_roots/
final/numbered_v7_manifest.json
final/numbered_v6_manifest.json
final/audit/final_freeze_v2/

QURAN_ROOTS_METHOD_PROVENANCE_AND_FREEZE_2026-08-25.md
QURAN_ROOTS_REPRODUCIBILITY_FILE_INDEX_2026-08-25.md
```

Do not perform this reduction without a separate archive/rights review; the list is a conceptual minimum, not a deletion instruction.

---

# 23. First files to inspect in any future investigation

For a question about the frozen corpus:

```text
1. final/audit/final_freeze_v2/report.json
2. final/numbered_v7_manifest.json
3. final/audit/final_freeze_v2/manifest.json
4. final/numbered_roots/<ID>_<ROOT>.json
5. output/root_synthesis_packets_v3.json
```

For provenance of an original production result:

```text
1. output/openai-batch-root-dictionary-v1/production-full/batch-001-output.jsonl
2. per-root attempt wrapper
3. collision recovery archive if applicable
4. repair stage reports if applicable
5. v7 manifest / freeze manifest
```

For rebuilding evidence:

```text
1. raw source snapshot
2. deterministic preparation scripts
3. source audit reports
4. build_root_synthesis_packets_v3.py
5. root_synthesis_packets_v3.json
```
