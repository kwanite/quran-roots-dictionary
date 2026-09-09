# Reproducibility

This project distinguishes three reproducibility goals.

## 1. Use

Consumers can use the frozen public dataset directly:

```text
data/roots/
data/root-index.json
```

No research source database or LLM call is required.

## 2. Verify

A reviewer can inspect:

- the preserved method/provenance documents;
- maintained pipeline scripts;
- stable source references;
- source-acquisition information;
- freeze reports;
- public release checksums;
- deterministic validation rules.

This supports methodological and claim-level investigation without requiring the entire historical debugging workspace.

## 3. Regenerate

A researcher can reacquire the upstream sources, recreate deterministic evidence outputs and root packets, then run a new synthesis.

The central research scripts are preserved under `pipeline/`.

Important distinction:

> A new LLM run is a regeneration under the documented method, not a promise of byte-for-byte reproduction of the 2026 synthesis outputs.

The evidence preparation and validation stages are deterministic; the LLM synthesis stage is not guaranteed to produce identical prose.

## Source order

The historical project documentation describes the construction chain in detail. The maintained high-level order is:

```text
QAC root extraction/index
→ Quran form inventory
→ Lane root matching/extraction/cross-reference closure
→ Maqayis matching/extraction
→ Mufradat matching/extraction
→ Quran contextual evidence preparation
→ combined evidence / packet v3
→ root dictionary synthesis
→ deterministic repair/validation
→ numbered/frozen corpus
→ v8 contextual rejoin
→ freeze-v3 audit
```

## Third-party data

Raw source datasets are not automatically copied into the public repository by the setup instructions.

Download them separately into an ignored local working area when reproducing the research pipeline.

See `sources/README.md`.
