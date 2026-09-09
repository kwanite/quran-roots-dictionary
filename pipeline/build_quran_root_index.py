#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path


# Extended Buckwalter -> Unicode Arabic for surface FORM / lemma text.
BW_TO_ARABIC = {
    "'": "ء", ">": "أ", "&": "ؤ", "<": "إ", "}": "ئ", "A": "ا",
    "b": "ب", "p": "ة", "t": "ت", "v": "ث", "j": "ج", "H": "ح",
    "x": "خ", "d": "د", "*": "ذ", "r": "ر", "z": "ز", "s": "س",
    "$": "ش", "S": "ص", "D": "ض", "T": "ط", "Z": "ظ", "E": "ع",
    "g": "غ", "_": "ـ", "f": "ف", "q": "ق", "k": "ك", "l": "ل",
    "m": "م", "n": "ن", "h": "ه", "w": "و", "Y": "ى", "y": "ي",
    "F": "ً", "N": "ٌ", "K": "ٍ", "a": "َ", "u": "ُ", "i": "ِ",
    "~": "ّ", "o": "ْ", "^": "ٓ", "#": "ٔ", "`": "ٰ", "{": "ٱ",
    ":": "ۜ", "@": "۟", '"': "۠", "[": "ۢ", ";": "ۣ", ",": "ۥ",
    ".": "ۦ", "!": "ۨ", "-": "۪", "+": "۫", "%": "۬", "]": "ۭ",
    " ": " ",
}

# ROOT is a normalized radical code, not ordinary surface orthography.
# In ROOT values, A represents a hamza radical, displayed by the corpus as أ.
ROOT_TO_ARABIC = {
    "$": "ش", "*": "ذ", "A": "أ", "D": "ض", "E": "ع", "H": "ح",
    "S": "ص", "T": "ط", "Z": "ظ", "b": "ب", "d": "د", "f": "ف",
    "g": "غ", "h": "ه", "j": "ج", "k": "ك", "l": "ل", "m": "م",
    "n": "ن", "q": "ق", "r": "ر", "s": "س", "t": "ت", "v": "ث",
    "w": "و", "x": "خ", "y": "ي", "z": "ز",
}

VERB_ASPECTS = {"PERF", "IMPF", "IMPV"}
CASES = {"NOM", "ACC", "GEN"}
STATES = {"DEF", "INDEF"}


def buckwalter_to_arabic(value: str) -> str:
    """Decode FORM/lemma orthography from Extended Buckwalter."""
    unknown = [ch for ch in value if ch not in BW_TO_ARABIC]
    if unknown:
        raise ValueError(
            f"Unknown Buckwalter character(s) {sorted(set(unknown))} in {value!r}"
        )
    return "".join(BW_TO_ARABIC[ch] for ch in value)


def root_to_arabic(root: str) -> tuple[list[str], str, str]:
    """
    Decode a corpus ROOT identifier into Arabic radicals.

    Returns:
        (letters, compact, spaced)

    Example:
        rHm -> (["ر", "ح", "م"], "رحم", "ر ح م")
    """
    try:
        letters = [ROOT_TO_ARABIC[ch] for ch in root]
    except KeyError as exc:
        raise ValueError(
            f"Unknown ROOT character {exc.args[0]!r} in root {root!r}"
        ) from None

    return letters, "".join(letters), " ".join(letters)


def parse_lemma_id(raw_lemma: str) -> dict:
    """
    Lemmas are Extended Buckwalter, but v0.4 also contains a trailing
    numeric discriminator, e.g. maE2. The discriminator is metadata
    and must not be rendered as Arabic.
    """
    match = re.fullmatch(r"(.*?)(\d+)?", raw_lemma)
    if not match:
        raise ValueError(f"Could not parse lemma ID: {raw_lemma!r}")

    buckwalter_base = match.group(1)
    discriminator = (
        int(match.group(2)) if match.group(2) is not None else None
    )

    return {
        "id": raw_lemma,
        "buckwalter": buckwalter_base,
        "discriminator": discriminator,
        "arabic": buckwalter_to_arabic(buckwalter_base),
    }


def location_parts(location: str) -> tuple[int, int, int, int]:
    """Parse '(surah:ayah:word:segment)'."""
    match = re.fullmatch(r"\((\d+):(\d+):(\d+):(\d+)\)", location)
    if not match:
        raise ValueError(f"Invalid LOCATION: {location!r}")
    return tuple(map(int, match.groups()))


def roman_form_number(token: str) -> str:
    """Convert '(IV)' to 'IV'."""
    return token[1:-1]


def sorted_counter(counter: Counter) -> dict:
    """Return an ordinary dict with deterministic key order."""
    return {key: counter[key] for key in sorted(counter)}


def build_root_index(input_file: Path) -> dict:
    # Aggregate structures.
    root_occurrences = Counter()
    root_word_locations = defaultdict(set)
    root_surahs = defaultdict(set)
    root_pos = defaultdict(Counter)
    root_lemmas = defaultdict(lambda: defaultdict(lambda: {
        "count": 0,
        "pos": Counter(),
    }))
    root_surface_forms = defaultdict(lambda: defaultdict(lambda: {
        "count": 0,
        "pos": Counter(),
    }))
    root_feature_counts = defaultdict(Counter)
    root_verb_forms = defaultdict(Counter)
    root_verb_aspects = defaultdict(Counter)
    root_verb_voice = defaultdict(Counter)
    root_derived = defaultdict(Counter)
    root_cases = defaultdict(Counter)
    root_states = defaultdict(Counter)
    root_special_classes = defaultdict(Counter)
    root_segment_locations = defaultdict(list)

    data_rows = 0
    root_rows = 0

    with input_file.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            line = line.rstrip("\r\n")

            if not line or line.startswith("#"):
                continue

            if line.startswith("LOCATION\tFORM\tTAG\tFEATURES"):
                continue

            columns = line.split("\t")
            if len(columns) != 4:
                raise ValueError(
                    f"Malformed line {line_number}: expected 4 TAB-separated "
                    f"columns, found {len(columns)}"
                )

            location, form, tag, features = columns
            data_rows += 1

            tokens = features.split("|")

            # ROOT-bearing rows in v0.4 are STEM rows, but do not assume
            # that blindly: explicitly find ROOT in the feature list.
            root = next(
                (token[5:] for token in tokens if token.startswith("ROOT:")),
                None,
            )
            if root is None:
                continue

            root_rows += 1

            lemma = next(
                (token[4:] for token in tokens if token.startswith("LEM:")),
                None,
            )

            surah, ayah, word, segment = location_parts(location)
            word_location = f"({surah}:{ayah}:{word})"

            root_occurrences[root] += 1
            root_word_locations[root].add(word_location)
            root_surahs[root].add(surah)
            root_pos[root][tag] += 1
            root_segment_locations[root].append(location)

            # Lemma aggregation.
            if lemma is not None:
                lemma_bucket = root_lemmas[root][lemma]
                lemma_bucket["count"] += 1
                lemma_bucket["pos"][tag] += 1

            # Surface segment aggregation.
            form_bucket = root_surface_forms[root][form]
            form_bucket["count"] += 1
            form_bucket["pos"][tag] += 1

            # Preserve useful raw grammatical feature frequencies.
            for token in tokens:
                if (
                    token == "STEM"
                    or token.startswith("POS:")
                    or token.startswith("LEM:")
                    or token.startswith("ROOT:")
                ):
                    continue
                root_feature_counts[root][token] += 1

            # Special grammatical class.
            for token in tokens:
                if token.startswith("SP:"):
                    root_special_classes[root][token[3:]] += 1

            # Case/state summaries.
            for token in tokens:
                if token in CASES:
                    root_cases[root][token] += 1
                elif token in STATES:
                    root_states[root][token] += 1

            # Verb-specific summaries.
            if tag == "V":
                explicit_form = next(
                    (
                        roman_form_number(token)
                        for token in tokens
                        if re.fullmatch(r"\([IVX]+\)", token)
                    ),
                    None,
                )

                # The corpus documents Form I as the default when omitted.
                root_verb_forms[root][explicit_form or "I"] += 1

                aspect = next(
                    (token for token in tokens if token in VERB_ASPECTS),
                    None,
                )
                if aspect is not None:
                    root_verb_aspects[root][aspect] += 1

                root_verb_voice[root][
                    "PASSIVE" if "PASS" in tokens else "ACTIVE"
                ] += 1

            # Derived nominal summaries.
            if "PCPL" in tokens and "ACT" in tokens:
                root_derived[root]["ACTIVE_PARTICIPLE"] += 1
            if "PCPL" in tokens and "PASS" in tokens:
                root_derived[root]["PASSIVE_PARTICIPLE"] += 1
            if "VN" in tokens:
                root_derived[root]["VERBAL_NOUN"] += 1

    roots_output = []

    for root in sorted(root_occurrences):
        letters, arabic, arabic_spaced = root_to_arabic(root)

        lemmas = []
        for lemma_id in sorted(root_lemmas[root]):
            parsed = parse_lemma_id(lemma_id)
            parsed["occurrence_count"] = root_lemmas[root][lemma_id]["count"]
            parsed["pos_counts"] = sorted_counter(
                root_lemmas[root][lemma_id]["pos"]
            )
            lemmas.append(parsed)

        surface_forms = []
        for raw_form in sorted(root_surface_forms[root]):
            surface_forms.append({
                "buckwalter": raw_form,
                "arabic": buckwalter_to_arabic(raw_form),
                "occurrence_count": root_surface_forms[root][raw_form]["count"],
                "pos_counts": sorted_counter(
                    root_surface_forms[root][raw_form]["pos"]
                ),
            })

        verb_count = sum(root_verb_forms[root].values())

        roots_output.append({
            "root": root,
            "arabic": arabic,
            "arabic_spaced": arabic_spaced,
            "radicals": letters,

            "occurrence_count": root_occurrences[root],
            "word_count": len(root_word_locations[root]),
            "surah_count": len(root_surahs[root]),
            "surahs": sorted(root_surahs[root]),

            "pos_counts": sorted_counter(root_pos[root]),

            "lemma_count": len(lemmas),
            "lemmas": lemmas,

            "surface_form_count": len(surface_forms),
            "surface_forms": surface_forms,

            "verb": {
                "occurrence_count": verb_count,
                "forms": sorted_counter(root_verb_forms[root]),
                "aspects": sorted_counter(root_verb_aspects[root]),
                "voice": sorted_counter(root_verb_voice[root]),
            },

            "derived_nominals": sorted_counter(root_derived[root]),
            "case_counts": sorted_counter(root_cases[root]),
            "state_counts": sorted_counter(root_states[root]),
            "special_class_counts": sorted_counter(
                root_special_classes[root]
            ),

            # Raw feature frequencies are kept because they allow later
            # analyses without re-reading the original file.
            "feature_counts": sorted_counter(root_feature_counts[root]),

            # These are deterministic join keys for adding a separate
            # word-by-word gloss/translation dataset later.
            "word_locations": sorted(
                root_word_locations[root],
                key=lambda x: tuple(map(int, x.strip("()").split(":"))),
            ),

            # Exact segment locations are also preserved.
            "segment_locations": sorted(
                root_segment_locations[root],
                key=lambda x: tuple(map(int, x.strip("()").split(":"))),
            ),
        })

    return {
        "metadata": {
            "source_file": input_file.name,
            "format": "Quranic Arabic Corpus morphology v0.4 root index",
            "data_rows_processed": data_rows,
            "root_bearing_rows": root_rows,
            "unique_root_count": len(roots_output),
            "translation_glosses_in_source_file": False,
            "translation_join_key": "(surah:ayah:word)",
            "notes": [
                "ROOT values are preserved exactly as corpus identifiers.",
                "Arabic root rendering uses a ROOT-specific radical map.",
                "In ROOT values, A is rendered as the hamza radical أ.",
                "Lemma IDs may have a trailing numeric discriminator such as 2.",
                "The numeric lemma discriminator is preserved but not rendered as Arabic.",
                "word_locations can be joined to a separate word-by-word gloss dataset.",
            ],
            "attribution": "Quranic Arabic Corpus (corpus.quran.com), morphology version 0.4",
        },
        "roots": roots_output,
    }


def main() -> None:
    # Always use the folder containing this Python script.
    script_dir = Path(__file__).resolve().parent

    default_input = script_dir / "quranic-corpus-morphology-0.4.txt"
    default_output = script_dir / "quran_roots_index.json"

    parser = argparse.ArgumentParser(
        description=(
            "Build a deterministic JSON index of every ROOT in the "
            "Quranic Arabic Corpus morphology v0.4 file."
        )
    )

    parser.add_argument(
        "input_file",
        nargs="?",
        type=Path,
        default=default_input,
        help=(
            "Path to quranic-corpus-morphology-0.4.txt "
            "(defaults to the file beside this script)"
        ),
    )

    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=default_output,
        help=(
            "Output JSON path "
            "(defaults to quran_roots_index.json beside this script)"
        ),
    )

    args = parser.parse_args()

    if not args.input_file.exists():
        raise FileNotFoundError(
            f"Could not find morphology file:\n{args.input_file}"
        )

    index = build_root_index(args.input_file)

    args.output.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Data rows processed: {index['metadata']['data_rows_processed']:,}")
    print(f"Root-bearing rows:    {index['metadata']['root_bearing_rows']:,}")
    print(f"Unique roots:         {index['metadata']['unique_root_count']:,}")
    print(f"JSON written to:      {args.output.resolve()}")


if __name__ == "__main__":
    main()