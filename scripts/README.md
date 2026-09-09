# Publication scripts

These scripts operate on copies and generated outputs. They do not edit the frozen research corpus.

## Build public release

```bash
python3 scripts/build_public_release.py \
  --source-roots /absolute/path/to/final/numbered_roots_v8 \
  --source-manifest /absolute/path/to/final/numbered_v8_manifest.json \
  --output data
```

The builder:

- requires 1,642 source root JSON files;
- copies each record through a JSON parse/write cycle;
- recursively removes all keys named `context_gloss`;
- writes `data/roots/`;
- writes `data/root-index.json`;
- writes `data/manifest.json`;
- writes `data/checksums.sha256`;
- never modifies source files.

It refuses to overwrite a non-empty `data/roots/` unless `--replace-generated` is supplied.

## Validate

```bash
python3 scripts/validate_public_release.py
```
