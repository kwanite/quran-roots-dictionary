#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import time
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import requests
    from requests.auth import HTTPBasicAuth
except ImportError as exc:
    raise RuntimeError(
        "This script requires requests.\n\n"
        "Install it with:\n"
        "/Library/Developer/CommandLineTools/usr/bin/python3 "
        "-m pip install --user requests"
    ) from exc


# ============================================================
# Paths
# ============================================================

SCRIPT_DIR = Path(__file__).resolve().parent

ENV_FILE = SCRIPT_DIR / ".env"

QAC_MORPHOLOGY_FILE = (
    SCRIPT_DIR / "quranic-corpus-morphology-0.4.txt"
)

OUTPUT_DIR = (
    SCRIPT_DIR
    / "sources"
    / "quran-foundation"
)

# Deliberately separate from the broken chapter-cache produced by v3.
CACHE_DIR = (
    OUTPUT_DIR
    / "page-cache-v4"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "qf_wbw_en.json"
)

REPORT_FILE = (
    OUTPUT_DIR
    / "qf_wbw_download_report.json"
)

SAMPLE_FILE = (
    OUTPUT_DIR
    / "qf_wbw_sample.json"
)


# ============================================================
# Quran Foundation
# ============================================================

AUTH_BASE_BY_ENV = {
    "prelive":
        "https://prelive-oauth2.quran.foundation",

    "production":
        "https://oauth2.quran.foundation",
}

API_BASE_BY_ENV = {
    "prelive":
        "https://apis-prelive.quran.foundation",

    "production":
        "https://apis.quran.foundation",
}


LANGUAGE = "en"
MUSHAF_ID = 1

# Quran Foundation documents Mushaf 1 as 604 pages.
FIRST_MUSHAF_PAGE = 1
LAST_MUSHAF_PAGE = 604

PER_PAGE = 50

REQUEST_TIMEOUT_SECONDS = 45
MAX_RETRIES = 5
INITIAL_RETRY_DELAY_SECONDS = 2.0
REQUEST_PAUSE_SECONDS = 0.08
TOKEN_REFRESH_MARGIN_SECONDS = 30


# ============================================================
# .env
# ============================================================

def load_simple_env(path: Path) -> None:
    if not path.exists():
        return

    for raw_line in path.read_text(
        encoding="utf-8"
    ).splitlines():
        line = raw_line.strip()

        if (
            not line
            or line.startswith("#")
            or "=" not in line
        ):
            continue

        key, value = line.split(
            "=",
            1,
        )

        key = key.strip()
        value = value.strip()

        if (
            len(value) >= 2
            and value[0] == value[-1]
            and value[0] in {"'", '"'}
        ):
            value = value[1:-1]

        if (
            key
            and key not in os.environ
        ):
            os.environ[key] = value


# ============================================================
# API client
# ============================================================

class QuranFoundationHTTPError(
    RuntimeError
):
    def __init__(
        self,
        status_code: int,
        url: str,
        body: str,
    ) -> None:
        self.status_code = status_code
        self.url = url
        self.body = body

        super().__init__(
            "Quran Foundation request failed.\n"
            f"URL: {url}\n"
            f"HTTP {status_code}\n"
            f"{body}"
        )


class QuranFoundationClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        environment: str,
    ) -> None:
        if (
            environment
            not in AUTH_BASE_BY_ENV
        ):
            raise ValueError(
                "QF_ENV must be prelive "
                "or production."
            )

        self.client_id = client_id
        self.client_secret = client_secret

        self.auth_base = (
            AUTH_BASE_BY_ENV[
                environment
            ]
        )

        self.api_base = (
            API_BASE_BY_ENV[
                environment
            ]
        )

        self._access_token = None
        self._token_expires_at = 0.0

        self.session = (
            requests.Session()
        )

        self.session.headers.update(
            {
                "Accept":
                    "application/json",

                "User-Agent":
                    "quran-root-research/1.0",
            }
        )

    def _request_token(
        self,
    ) -> None:
        url = (
            f"{self.auth_base}"
            "/oauth2/token"
        )

        try:
            response = (
                self.session.post(
                    url,

                    auth=HTTPBasicAuth(
                        self.client_id,
                        self.client_secret,
                    ),

                    headers={
                        "Content-Type":
                            "application/"
                            "x-www-form-urlencoded"
                    },

                    data={
                        "grant_type":
                            "client_credentials",

                        "scope":
                            "content",
                    },

                    timeout=(
                        REQUEST_TIMEOUT_SECONDS
                    ),
                )
            )

        except requests.RequestException as exc:
            raise RuntimeError(
                "Could not connect to "
                "Quran Foundation OAuth:\n"
                f"{exc}"
            ) from exc

        if not response.ok:
            raise QuranFoundationHTTPError(
                response.status_code,
                response.url,
                response.text,
            )

        payload = response.json()

        token = payload.get(
            "access_token"
        )

        if not token:
            raise RuntimeError(
                "OAuth response contained "
                "no access_token."
            )

        expires_in = int(
            payload.get(
                "expires_in",
                3600,
            )
        )

        self._access_token = token

        self._token_expires_at = (
            time.time()
            + expires_in
            - TOKEN_REFRESH_MARGIN_SECONDS
        )

    def token(
        self,
    ) -> str:
        if (
            self._access_token is None
            or time.time()
            >= self._token_expires_at
        ):
            print(
                "  requesting/refreshing "
                "access token..."
            )

            self._request_token()

        return self._access_token

    def get_json(
        self,
        path: str,
        params: dict[str, Any]
        | None = None,
    ) -> dict:
        url = (
            f"{self.api_base}{path}"
        )

        delay = (
            INITIAL_RETRY_DELAY_SECONDS
        )

        for attempt in range(
            1,
            MAX_RETRIES + 1,
        ):
            try:
                response = (
                    self.session.get(
                        url,

                        params=params,

                        headers={
                            "x-auth-token":
                                self.token(),

                            "x-client-id":
                                self.client_id,
                        },

                        timeout=(
                            REQUEST_TIMEOUT_SECONDS
                        ),
                    )
                )

            except requests.RequestException as exc:
                if attempt < MAX_RETRIES:
                    print(
                        "  network error; "
                        f"retrying in "
                        f"{delay:.1f}s..."
                    )

                    time.sleep(delay)
                    delay *= 2
                    continue

                raise RuntimeError(
                    "Network request failed:\n"
                    f"{exc}"
                ) from exc

            if (
                response.status_code == 401
                and attempt < MAX_RETRIES
            ):
                self._access_token = None
                self._token_expires_at = 0

                print(
                    "  token rejected; "
                    "refreshing..."
                )

                continue

            if (
                response.status_code
                in {
                    429,
                    500,
                    502,
                    503,
                    504,
                }
                and attempt < MAX_RETRIES
            ):
                print(
                    f"  HTTP "
                    f"{response.status_code}; "
                    f"retrying in "
                    f"{delay:.1f}s..."
                )

                time.sleep(delay)
                delay *= 2
                continue

            if not response.ok:
                raise QuranFoundationHTTPError(
                    response.status_code,
                    response.url,
                    response.text,
                )

            try:
                payload = (
                    response.json()
                )

            except ValueError as exc:
                raise RuntimeError(
                    "API returned non-JSON.\n"
                    f"URL: {response.url}\n"
                    f"{response.text[:2000]}"
                ) from exc

            return payload

        raise RuntimeError(
            "Request exhausted retries."
        )


# ============================================================
# QAC reference locations
# ============================================================

def load_qac_word_locations(
    path: Path,
) -> set[str]:
    locations = set()

    with path.open(
        "r",
        encoding="utf-8",
    ) as handle:
        for raw_line in handle:
            line = raw_line.rstrip(
                "\r\n"
            )

            if (
                not line
                or line.startswith("#")
            ):
                continue

            parts = line.split("\t")

            if len(parts) != 4:
                continue

            location = parts[0]

            if not (
                location.startswith("(")
                and location.endswith(")")
            ):
                continue

            nums = (
                location[1:-1]
                .split(":")
            )

            if len(nums) != 4:
                continue

            surah, ayah, word, _ = nums

            locations.add(
                f"{int(surah)}:"
                f"{int(ayah)}:"
                f"{int(word)}"
            )

    return locations


# ============================================================
# Normalization
# ============================================================

def normalize_word(
    verse: dict,
    word: dict,
) -> dict | None:
    verse_key = (
        word.get("verse_key")
        or verse.get("verse_key")
    )

    position = word.get(
        "position"
    )

    if (
        not verse_key
        or position is None
    ):
        return None

    translation = (
        word.get("translation")
        or {}
    )

    transliteration = (
        word.get("transliteration")
        or {}
    )

    return {
        "qf_word_id":
            word.get("id"),

        "verse_key":
            verse_key,

        "position":
            int(position),

        "char_type_name":
            word.get(
                "char_type_name"
            ),

        "text_uthmani":
            word.get(
                "text_uthmani"
            ),

        "text_imlaei":
            word.get(
                "text_imlaei"
            ),

        "translation_en":
            translation.get(
                "text"
            ),

        "translation_language":
            translation.get(
                "language_name"
            ),

        "transliteration_en":
            transliteration.get(
                "text"
            ),
    }


# ============================================================
# Page fetching
# ============================================================

def page_cache_path(
    mushaf_page: int,
) -> Path:
    return (
        CACHE_DIR
        / f"page_{mushaf_page:03d}.json"
    )


def load_page_cache(
    mushaf_page: int,
) -> list[dict] | None:
    path = page_cache_path(
        mushaf_page
    )

    if not path.exists():
        return None

    try:
        payload = json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except (
        OSError,
        json.JSONDecodeError,
    ):
        return None

    verses = payload.get(
        "verses"
    )

    # Never trust an empty cache file.
    if (
        not isinstance(verses, list)
        or not verses
    ):
        return None

    return verses


def save_page_cache(
    mushaf_page: int,
    verses: list[dict],
) -> None:
    path = page_cache_path(
        mushaf_page
    )

    path.write_text(
        json.dumps(
            {
                "mushaf":
                    MUSHAF_ID,

                "page":
                    mushaf_page,

                "verses":
                    verses,
            },
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )


def fetch_mushaf_page(
    client: QuranFoundationClient,
    mushaf_page: int,
) -> list[dict]:
    """
    Quran Foundation documented route:

        GET /content/api/v4/verses/by_page/{page}

    We follow pagination defensively even though a Mushaf page is
    normally small.
    """
    all_verses = []

    api_page = 1

    while True:
        payload = client.get_json(
            (
                "/content/api/v4/"
                f"verses/by_page/"
                f"{mushaf_page}"
            ),

            params={
                "language":
                    LANGUAGE,

                "mushaf":
                    MUSHAF_ID,

                "words":
                    "true",

                "word_fields":
                    "text_uthmani,"
                    "text_imlaei",

                "per_page":
                    PER_PAGE,

                "page":
                    api_page,
            },
        )

        # Hard validation of response shape.
        if "verses" not in payload:
            raise RuntimeError(
                "by_page response contained "
                "no top-level 'verses' array.\n"
                f"Mushaf page: {mushaf_page}\n"
                "Top-level keys: "
                f"{sorted(payload.keys())}\n"
                "Response preview:\n"
                f"{json.dumps(payload, ensure_ascii=False)[:3000]}"
            )

        verses = payload[
            "verses"
        ]

        if not isinstance(
            verses,
            list,
        ):
            raise RuntimeError(
                "'verses' was not a list "
                f"for Mushaf page "
                f"{mushaf_page}."
            )

        all_verses.extend(
            verses
        )

        pagination = (
            payload.get("pagination")
            or {}
        )

        next_page = (
            pagination.get(
                "next_page"
            )
        )

        if not next_page:
            break

        api_page = int(
            next_page
        )

        time.sleep(
            REQUEST_PAUSE_SECONDS
        )

    if not all_verses:
        raise RuntimeError(
            "Quran Foundation returned ZERO "
            "verses for a valid Mushaf page.\n"
            f"Mushaf: {MUSHAF_ID}\n"
            f"Page: {mushaf_page}\n\n"
            "Stopping instead of silently "
            "producing an incomplete dataset."
        )

    return all_verses


# ============================================================
# Dataset merge
# ============================================================

def records_equivalent(
    a: dict,
    b: dict,
) -> bool:
    """
    Ignore qf_word_id when detecting duplicates because the same
    Quran word may be surfaced through overlapping page responses.
    """
    keys = [
        "verse_key",
        "position",
        "char_type_name",
        "text_uthmani",
        "text_imlaei",
        "translation_en",
        "translation_language",
        "transliteration_en",
    ]

    return all(
        a.get(key) == b.get(key)
        for key in keys
    )


def location_sort_key(
    location: str,
) -> tuple[int, int, int]:
    return tuple(
        int(part)
        for part in location.split(":")
    )


# ============================================================
# Main
# ============================================================

def main() -> None:
    load_simple_env(
        ENV_FILE
    )

    client_id = os.getenv(
        "QF_CLIENT_ID"
    )

    client_secret = os.getenv(
        "QF_CLIENT_SECRET"
    )

    environment = os.getenv(
        "QF_ENV",
        "prelive",
    ).strip().lower()

    if not client_id or not client_secret:
        raise RuntimeError(
            "Missing QF_CLIENT_ID or "
            "QF_CLIENT_SECRET in .env."
        )

    if not QAC_MORPHOLOGY_FILE.exists():
        raise FileNotFoundError(
            f"Missing QAC morphology file:\n"
            f"{QAC_MORPHOLOGY_FILE}"
        )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    CACHE_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    qac_locations = (
        load_qac_word_locations(
            QAC_MORPHOLOGY_FILE
        )
    )

    print(
        "Quran Foundation WBW "
        "page-based downloader v4"
    )

    print(
        f"Environment: {environment}"
    )

    print(
        f"QAC target word locations: "
        f"{len(qac_locations):,}"
    )

    client = QuranFoundationClient(
        client_id,
        client_secret,
        environment,
    )

    # --------------------------------------------------------
    # Preflight
    # --------------------------------------------------------

    print()
    print(
        "Preflight: checking Quran "
        "Foundation chapter catalogue..."
    )

    chapters_payload = client.get_json(
        "/content/api/v4/chapters",
        params={
            "language":
                LANGUAGE
        },
    )

    chapters = chapters_payload.get(
        "chapters",
        []
    )

    print(
        f"  chapters returned: "
        f"{len(chapters):,}"
    )

    if len(chapters) != 114:
        raise RuntimeError(
            "Prelive chapter catalogue did "
            f"not return 114 chapters; got "
            f"{len(chapters)}.\n"
            "Stopping before the bulk download."
        )

    # Check pages from beginning, middle, end BEFORE doing 604 pages.
    preflight_pages = [
        1,
        50,
        300,
        604,
    ]

    print()
    print(
        "Preflight: checking page-based "
        "verse retrieval..."
    )

    for mushaf_page in preflight_pages:
        cached = load_page_cache(
            mushaf_page
        )

        if cached is not None:
            verses = cached
            source = "cache"
        else:
            verses = fetch_mushaf_page(
                client,
                mushaf_page,
            )

            save_page_cache(
                mushaf_page,
                verses,
            )

            source = "API"

        verse_keys = [
            verse.get("verse_key")
            for verse in verses
            if verse.get("verse_key")
        ]

        print(
            f"  page {mushaf_page:03d}: "
            f"{len(verses)} verse records "
            f"({source}) "
            f"{verse_keys[:1]} ... "
            f"{verse_keys[-1:]}"
        )

        if not verse_keys:
            raise RuntimeError(
                "Preflight page returned no "
                "verse keys."
            )

    # --------------------------------------------------------
    # Bulk page download
    # --------------------------------------------------------

    print()
    print(
        "Fetching all 604 Mushaf pages..."
    )

    words_by_location: dict[
        str,
        dict
    ] = {}

    duplicate_locations = Counter()
    conflicting_duplicates = []

    char_type_counts = Counter()

    verse_keys_seen = set()
    cached_page_count = 0
    api_page_count = 0

    for mushaf_page in range(
        FIRST_MUSHAF_PAGE,
        LAST_MUSHAF_PAGE + 1,
    ):
        print(
            f"  Mushaf page "
            f"{mushaf_page:03d}/604..."
        )

        cached = load_page_cache(
            mushaf_page
        )

        if cached is not None:
            verses = cached
            cached_page_count += 1

            print(
                "    using cached page"
            )

        else:
            verses = fetch_mushaf_page(
                client,
                mushaf_page,
            )

            save_page_cache(
                mushaf_page,
                verses,
            )

            api_page_count += 1

            time.sleep(
                REQUEST_PAUSE_SECONDS
            )

        for verse in verses:
            verse_key = verse.get(
                "verse_key"
            )

            if verse_key:
                verse_keys_seen.add(
                    verse_key
                )

            for word in verse.get(
                "words",
                []
            ):
                record = normalize_word(
                    verse,
                    word,
                )

                if record is None:
                    continue

                char_type = (
                    record.get(
                        "char_type_name"
                    )
                    or "(missing)"
                )

                char_type_counts[
                    char_type
                ] += 1

                if char_type != "word":
                    continue

                location = (
                    f"{record['verse_key']}:"
                    f"{record['position']}"
                )

                existing = (
                    words_by_location.get(
                        location
                    )
                )

                if existing is not None:
                    duplicate_locations[
                        location
                    ] += 1

                    if not records_equivalent(
                        existing,
                        record,
                    ):
                        conflicting_duplicates.append(
                            {
                                "location":
                                    location,

                                "existing":
                                    existing,

                                "new":
                                    record,

                                "mushaf_page":
                                    mushaf_page,
                            }
                        )

                    continue

                words_by_location[
                    location
                ] = record

    # --------------------------------------------------------
    # QAC reconciliation
    # --------------------------------------------------------

    qf_locations = set(
        words_by_location
    )

    matching = (
        qac_locations
        & qf_locations
    )

    missing = sorted(
        qac_locations
        - qf_locations,
        key=location_sort_key,
    )

    extra = sorted(
        qf_locations
        - qac_locations,
        key=location_sort_key,
    )

    coverage_percent = (
        len(matching)
        / len(qac_locations)
        * 100
    )

    report = {
        "metadata": {
            "source":
                "Quran Foundation "
                "Content API v4",

            "downloader_version":
                4,

            "download_strategy":
                "mushaf_pages",

            "environment":
                environment,

            "language":
                LANGUAGE,

            "mushaf":
                MUSHAF_ID,

            "join_key":
                "surah:ayah:word",
        },

        "summary": {
            "chapter_catalogue_count":
                len(chapters),

            "mushaf_pages_expected":
                LAST_MUSHAF_PAGE,

            "mushaf_pages_from_cache":
                cached_page_count,

            "mushaf_pages_from_api":
                api_page_count,

            "unique_verse_keys_seen":
                len(verse_keys_seen),

            "qf_unique_word_locations":
                len(qf_locations),

            "qac_unique_word_locations":
                len(qac_locations),

            "matching_locations":
                len(matching),

            "coverage_percent":
                round(
                    coverage_percent,
                    4,
                ),

            "missing_qac_locations":
                len(missing),

            "extra_qf_locations":
                len(extra),

            "duplicate_location_count":
                sum(
                    duplicate_locations.values()
                ),

            "duplicate_unique_locations":
                len(
                    duplicate_locations
                ),

            "conflicting_duplicate_count":
                len(
                    conflicting_duplicates
                ),

            "char_type_counts":
                dict(
                    sorted(
                        char_type_counts.items()
                    )
                ),
        },

        "missing_locations":
            missing,

        "extra_locations":
            extra,

        "conflicting_duplicates":
            conflicting_duplicates[:200],

        "most_repeated_locations": [
            {
                "location":
                    location,

                "extra_appearances":
                    count,
            }
            for location, count
            in duplicate_locations.most_common(
                100
            )
        ],
    }

    REPORT_FILE.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    # --------------------------------------------------------
    # Do NOT call it complete unless validation is sane.
    # --------------------------------------------------------

    if coverage_percent < 99.0:
        print()
        print("=" * 60)
        print(
            "VALIDATION FAILED — "
            "OUTPUT NOT ACCEPTED"
        )
        print("=" * 60)

        print(
            f"QAC words:       "
            f"{len(qac_locations):,}"
        )

        print(
            f"QF words:        "
            f"{len(qf_locations):,}"
        )

        print(
            f"Matching:        "
            f"{len(matching):,}"
        )

        print(
            f"Coverage:        "
            f"{coverage_percent:.2f}%"
        )

        print(
            f"Missing:         "
            f"{len(missing):,}"
        )

        print(
            f"Extra:           "
            f"{len(extra):,}"
        )

        print()
        print(
            "Diagnostic report written to:\n"
            f"{REPORT_FILE}"
        )

        raise RuntimeError(
            "Quran Foundation/QAC word-location "
            "coverage is below 99%. "
            "The full dataset was NOT written."
        )

    # --------------------------------------------------------
    # Accepted source dataset
    # --------------------------------------------------------

    output = {
        "metadata": {
            "source":
                "Quran Foundation "
                "Content API v4",

            "downloader_version":
                4,

            "download_strategy":
                "mushaf_pages",

            "environment":
                environment,

            "language":
                LANGUAGE,

            "mushaf":
                MUSHAF_ID,

            "join_key":
                "surah:ayah:word",

            "important_note":
                (
                    "Word-by-word English "
                    "renderings are contextual "
                    "glosses, not complete "
                    "root definitions."
                ),
        },

        "summary":
            report["summary"],

        "words":
            dict(
                sorted(
                    words_by_location.items(),
                    key=lambda item:
                        location_sort_key(
                            item[0]
                        ),
                )
            ),
    }

    OUTPUT_FILE.write_text(
        json.dumps(
            output,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    sample_keys = [
        "1:1:1",
        "1:1:2",
        "1:1:3",
        "1:1:4",
        "2:255:1",
        "2:255:2",
        "3:1:1",
        "3:2:1",
        "55:1:1",
        "55:2:1",
        "112:1:1",
        "114:6:1",
    ]

    sample = {
        "metadata": {
            "purpose":
                "Quran Foundation WBW "
                "page-based download sample"
        },

        "words": {
            key:
                words_by_location.get(
                    key
                )
            for key in sample_keys
        },
    }

    SAMPLE_FILE.write_text(
        json.dumps(
            sample,
            ensure_ascii=False,
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print()
    print("=" * 60)
    print(
        "QURAN FOUNDATION WBW "
        "DOWNLOAD ACCEPTED"
    )
    print("=" * 60)

    print(
        f"Unique verses seen: "
        f"{len(verse_keys_seen):,}"
    )

    print(
        f"QF word locations:  "
        f"{len(qf_locations):,}"
    )

    print(
        f"QAC word locations: "
        f"{len(qac_locations):,}"
    )

    print(
        f"Matching locations: "
        f"{len(matching):,}"
    )

    print(
        f"Coverage:           "
        f"{coverage_percent:.4f}%"
    )

    print(
        f"Missing:            "
        f"{len(missing):,}"
    )

    print(
        f"Extra:              "
        f"{len(extra):,}"
    )

    print(
        f"Conflicting dupes:  "
        f"{len(conflicting_duplicates):,}"
    )

    print()
    print(
        "Full source dataset:\n"
        f"{OUTPUT_FILE}"
    )

    print()
    print(
        "Audit report:\n"
        f"{REPORT_FILE}"
    )

    print()
    print(
        "Small sample:\n"
        f"{SAMPLE_FILE}"
    )


if __name__ == "__main__":
    main()
