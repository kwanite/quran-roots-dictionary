# Contributing

Contributions are welcome through GitHub issues and pull requests.

## Good contributions

Examples include:

- evidence-backed correction to a definition or usage condition;
- missing or incorrect lexical source reference;
- incorrect Quran form mapping or accounting;
- validator improvement;
- reproducibility or documentation correction;
- website accessibility or usability improvement;
- test coverage.

## Semantic/data corrections

Do not submit an unexplained edit to a root JSON file.

A semantic correction should identify:

1. root ID and exact QAC root;
2. affected `public_form_id`, `sense_id`, `meaning_id`, or other field;
3. current value;
4. proposed value;
5. supporting lexical/Quranic evidence;
6. source reference(s);
7. whether the proposal changes Quran-form accounting, occurrence counts, or IDs.

See `docs/CONTRIBUTING_DATA_CORRECTIONS.md`.

## Pull request checks

Pull requests that change the public dataset must pass:

```bash
python3 scripts/validate_public_release.py
```

The GitHub workflow runs the same release checks.

## Stable identities

Do not:

- casefold or merge exact QAC roots;
- change a stable root ID merely for aesthetics;
- fuzzy-match roots or source IDs;
- silently invent source references;
- silently remove ambiguous evidence.

## Generated files

`data/roots/`, `data/root-index.json`, `data/manifest.json`, and `data/checksums.sha256` are generated publication artifacts. If the source corpus changes, regenerate them with `scripts/build_public_release.py`.

## Discussion before large changes

Open an issue before proposing a schema-breaking change, changing the evidence architecture, replacing a canonical source role, or altering stable root IDs.
