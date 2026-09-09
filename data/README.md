# Public data

`data/roots/` is generated from the project's frozen v8 root corpus by:

```bash
python3 scripts/build_public_release.py \
  --source-roots /path/to/final/numbered_roots_v8 \
  --source-manifest /path/to/final/numbered_v8_manifest.json \
  --output data
```

The public build removes all `context_gloss` fields from the root JSON before writing the release copy.

It does **not** edit the source corpus.

Generated files:

- `roots/*.json`
- `root-index.json`
- `manifest.json`
- `checksums.sha256`

`root-index.json` is the supported way to resolve a numeric root ID or exact case-sensitive QAC root to a filename.
