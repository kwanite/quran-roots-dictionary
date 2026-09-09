# Validation

The research corpus reached semantic freeze through deterministic validation after synthesis and conservative repair.

The public repository adds a smaller publication-layer validator:

```bash
python3 scripts/validate_public_release.py
```

It checks:

- exactly 1,642 public root JSON files;
- filenames begin with IDs `0001` through `1642`;
- every file parses as JSON;
- filename ID uniqueness;
- exact root uniqueness;
- required top-level structural fields;
- `quranic_forms` is a list;
- public form IDs and sense IDs are not duplicated within a root;
- every Quran example `sense_id` points to a sense in the same public form;
- no `context_gloss` field survived public transformation;
- `data/root-index.json` agrees with files;
- `data/manifest.json` reports a complete 1,642-root release.

This publication validator does not replace the deeper research validator in `pipeline/synthesize_root_dictionary_v11.py` and the freeze audit.

## Research validation principles

The deeper validator enforced, among other things:

- QAC form accounting;
- Quran example location validity;
- occurrence counts;
- unique/stable semantic IDs;
- lexical source-reference validity;
- direct lexical support for Quranic senses;
- Lane evidence-unit coverage;
- source-to-claim linkage.

See the preserved research documentation under `docs/research-record/`.
