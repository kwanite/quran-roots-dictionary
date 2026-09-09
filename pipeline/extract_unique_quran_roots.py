from pathlib import Path

# Input file should be in the same folder as this script.
INPUT_FILE = Path("quranic-corpus-morphology-0.4.txt")

# Output: one unique raw corpus root per line.
OUTPUT_FILE = Path("unique_roots.txt")


def extract_unique_roots(input_file: Path) -> list[str]:
    """
    Read the Quranic Arabic Corpus morphology file and return
    all unique ROOT values in deterministic sorted order.
    """

    roots = set()

    with input_file.open("r", encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            # Remove only the newline characters.
            # Do NOT split the line on ordinary whitespace because FORM can
            # contain an internal ASCII space in at least one corpus record.
            line = line.rstrip("\r\n")

            # Skip blank lines and copyright/comment lines.
            if not line or line.startswith("#"):
                continue

            # Skip the TSV header.
            if line.startswith("LOCATION\tFORM\tTAG\tFEATURES"):
                continue

            # Each morphology data row has exactly four TAB-separated fields:
            # LOCATION, FORM, TAG, FEATURES.
            columns = line.split("\t")

            if len(columns) != 4:
                raise ValueError(
                    f"Malformed row at line {line_number}: "
                    f"expected 4 tab-separated columns, found {len(columns)}"
                )

            location, form, tag, features = columns

            # FEATURES is pipe-delimited, for example:
            # STEM|POS:N|LEM:{som|ROOT:smw|M|GEN
            for feature in features.split("|"):
                if feature.startswith("ROOT:"):
                    root = feature.split(":", 1)[1]

                    if not root:
                        raise ValueError(
                            f"Empty ROOT value at line {line_number}"
                        )

                    roots.add(root)

                    # A row has at most one ROOT feature, so stop scanning
                    # the feature list for this row.
                    break

    # Sorting makes the output deterministic and independent of encounter order.
    return sorted(roots)


def main():
    if not INPUT_FILE.exists():
        raise FileNotFoundError(
            f"Could not find input file: {INPUT_FILE.resolve()}\n"
            "Put quranic-corpus-morphology-0.4.txt in the same folder "
            "as this Python script."
        )

    roots = extract_unique_roots(INPUT_FILE)

    OUTPUT_FILE.write_text(
        "\n".join(roots) + "\n",
        encoding="utf-8"
    )

    print(f"Unique roots found: {len(roots)}")
    print(f"Output written to: {OUTPUT_FILE.resolve()}")


if __name__ == "__main__":
    main()
