"""Offline candidate search backed by the official bulk address datasets.

The Juso search API is the default evidence source, but the same official data is
published as downloadable full datasets at
https://business.juso.go.kr/addrlink/attrbDBDwld/attrbDBDwldList.do?cPath=99MD.

This module indexes those files into SQLite and exposes ``BulkSearchClient``,
which satisfies the same :class:`~juso_key.resolver.SearchClient` protocol as
``JusoSearchClient``. Matching, ranking, and the confirmed/candidate/unmatched
decision stay in :mod:`juso_key.resolver` and are not duplicated here, so an
offline run and an API run are judged by identical rules.

Source of the address key
-------------------------
The key this module returns is the 25-character 관리번호 of the 주소DB, which is
the same value the search API returns as ``bdMgtSn``. This matters: the
road-name address distribution files (``rnaddrkor_*.txt``) carry a *different*
26-character 도로명주소 관리번호 in their first column, and that value does not
appear in the 주소DB key space at all. Indexing those files would populate the
address key with an identifier the API never returns, so the 주소DB is used as
the authoritative source instead.

Datasets used (2026-07 full release), all CP949 with CRLF and no header row:

- ``주소DB/주소_<시도>.txt`` address records, 11 fields, PK 관리번호
- ``주소DB/지번_<시도>.txt`` land-lot records, 11 fields, FK 관리번호
- ``주소DB/부가정보_<시도>.txt`` supplementary records, 9 fields, FK 관리번호
- ``주소DB/개선_도로명코드_전체분.txt`` road-code table, 17 fields
- ``영문주소DB/rn_<region>.txt`` English address DB, 18 fields, FK 관리번호
"""

from __future__ import annotations

import re
import sqlite3
import unicodedata
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

from .resolver import Candidate, compact

BULK_EVIDENCE_SOURCE = "Juso bulk dataset (주소DB full release)"
BULK_ENCODING = "cp949"
DEFAULT_LIMIT = 10
INSERT_BATCH = 50_000

ADDRESS_FIELDS = 11
JIBUN_FIELDS = 11
EXTRA_FIELDS = 9
ROADCODE_FIELDS = 17
ENGLISH_FIELDS = 18

# 주소_<시도>.txt
A_MGMT, A_ROAD_CODE, A_EMD_SEQ, A_UNDERGROUND = 0, 1, 2, 3
A_BLD_MAIN, A_BLD_SUB, A_ZIP = 4, 5, 6
A_PREV_MGMT, A_DETAIL_FLAG = 9, 10

# 지번_<시도>.txt
J_MGMT, J_SEQ, J_LDONG_CODE, J_SIDO, J_SGG, J_EMD, J_RI = 0, 1, 2, 3, 4, 5, 6
J_SAN, J_MAIN, J_SUB, J_REPRESENTATIVE = 7, 8, 9, 10

# 부가정보_<시도>.txt
X_MGMT, X_HDONG_CODE, X_HDONG, X_ZIP = 0, 1, 2, 3
X_LEDGER_NAME, X_SGG_NAME, X_APARTMENT = 6, 7, 8

# 개선_도로명코드_전체분.txt
R_ROAD_CODE, R_ROAD, R_ROAD_EN, R_EMD_SEQ = 0, 1, 2, 3
R_SIDO, R_SIDO_EN, R_SGG, R_SGG_EN, R_EMD, R_EMD_EN = 4, 5, 6, 7, 8, 9

# rn_<region>.txt (영문주소DB)
E_SIDO_EN, E_SGG_EN, E_EMD_EN, E_ROAD_EN, E_MGMT = 1, 2, 3, 9, 13

SCHEMA = """
CREATE TABLE IF NOT EXISTS building (
    mgmt_no      TEXT NOT NULL,
    road_code    TEXT NOT NULL,
    emd_seq      TEXT NOT NULL,
    sido         TEXT NOT NULL,
    sgg          TEXT NOT NULL,
    emd          TEXT NOT NULL,
    road         TEXT NOT NULL,
    road_norm    TEXT NOT NULL,
    underground  INTEGER NOT NULL,
    bld_main     INTEGER NOT NULL,
    bld_sub      INTEGER NOT NULL,
    zip          TEXT NOT NULL,
    detail_flag  INTEGER NOT NULL,
    ldong_code   TEXT NOT NULL,
    jibun_emd    TEXT NOT NULL,
    jibun_ri     TEXT NOT NULL,
    san          TEXT NOT NULL,
    jibun_main   INTEGER NOT NULL,
    jibun_sub    INTEGER NOT NULL,
    hdong_code   TEXT NOT NULL,
    hdong        TEXT NOT NULL,
    bld_name     TEXT NOT NULL,
    apartment    INTEGER NOT NULL,
    region       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS english (
    mgmt_no TEXT NOT NULL,
    sido    TEXT NOT NULL,
    sgg     TEXT NOT NULL,
    emd     TEXT NOT NULL,
    road    TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS build_meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""

INDEXES = """
CREATE INDEX IF NOT EXISTS idx_building_road
    ON building (road_norm, bld_main, bld_sub, underground);
CREATE INDEX IF NOT EXISTS idx_building_roadcode
    ON building (road_code, bld_main, bld_sub, underground);
CREATE INDEX IF NOT EXISTS idx_building_jibun
    ON building (jibun_emd, jibun_main, jibun_sub);
CREATE INDEX IF NOT EXISTS idx_building_mgmt ON building (mgmt_no);
CREATE INDEX IF NOT EXISTS idx_english_mgmt ON english (mgmt_no);
"""

ROAD_PATTERN = re.compile(
    r"(?P<road>[가-힣A-Za-z0-9·]+(?:로|길))"
    r"\s*(?P<under>지하)?\s*"
    r"(?P<main>\d+)"
    r"(?:\s*-\s*(?P<sub>\d+))?"
)
JIBUN_PATTERN = re.compile(
    r"(?P<emd>[가-힣]+(?:동|리|가))"
    r"\s*(?P<san>산)?\s*"
    r"(?P<main>\d+)"
    r"(?:\s*-\s*(?P<sub>\d+))?"
)


def as_int(value: str) -> int:
    stripped = value.strip()
    return int(stripped) if stripped.isdigit() else 0


@dataclass(frozen=True)
class RoadQuery:
    road: str
    road_norm: str
    underground: int
    bld_main: int
    bld_sub: int


@dataclass(frozen=True)
class JibunQuery:
    emd: str
    jibun_main: int
    jibun_sub: int


@dataclass(frozen=True)
class BuildReport:
    db_path: str
    regions: int
    address_rows: int
    jibun_rows: int
    extra_rows: int
    english_rows: int
    road_codes: int
    unresolved_road_code: int
    distinct_keys: int
    distinct_sido: tuple[str, ...]


def parse_road_query(value: str) -> RoadQuery | None:
    """Extract road name and building number from a free-form address string."""

    normalized = unicodedata.normalize("NFKC", value)
    matches = list(ROAD_PATTERN.finditer(normalized))
    if not matches:
        return None
    match = matches[-1]
    road = match.group("road")
    return RoadQuery(
        road=road,
        road_norm=compact(road),
        underground=1 if match.group("under") else 0,
        bld_main=int(match.group("main")),
        bld_sub=int(match.group("sub") or 0),
    )


def parse_jibun_query(value: str) -> JibunQuery | None:
    """Extract legal-district name and lot number from a free-form address string."""

    normalized = unicodedata.normalize("NFKC", value)
    matches = list(JIBUN_PATTERN.finditer(normalized))
    if not matches:
        return None
    match = matches[-1]
    return JibunQuery(
        emd=match.group("emd"),
        jibun_main=int(match.group("main")),
        jibun_sub=int(match.group("sub") or 0),
    )


def iter_pipe_rows(path: Path, expected_fields: int) -> Iterator[list[str]]:
    with path.open(encoding=BULK_ENCODING, errors="replace") as handle:
        for line in handle:
            fields = line.rstrip("\r\n").split("|")
            if len(fields) < expected_fields:
                continue
            yield fields


def load_road_codes(path: Path) -> dict[tuple[str, str], tuple[str, str, str, str, str]]:
    """Map (도로명코드, 읍면동일련번호) to Korean and English place names."""

    table: dict[tuple[str, str], tuple[str, str, str, str, str]] = {}
    for fields in iter_pipe_rows(path, ROADCODE_FIELDS):
        key = (fields[R_ROAD_CODE].strip(), fields[R_EMD_SEQ].strip())
        table[key] = (
            fields[R_SIDO].strip(),
            fields[R_SGG].strip(),
            fields[R_EMD].strip(),
            fields[R_ROAD].strip(),
            fields[R_ROAD_EN].strip(),
        )
    return table


def load_representative_jibun(path: Path) -> dict[str, tuple[str, str, str, str, int, int]]:
    """Keep one land-lot record per 관리번호, preferring the representative lot."""

    table: dict[str, tuple[str, str, str, str, int, int]] = {}
    for fields in iter_pipe_rows(path, JIBUN_FIELDS):
        mgmt = fields[J_MGMT].strip()
        representative = fields[J_REPRESENTATIVE].strip() == "1"
        if mgmt in table and not representative:
            continue
        table[mgmt] = (
            fields[J_LDONG_CODE].strip(),
            fields[J_EMD].strip(),
            fields[J_RI].strip(),
            fields[J_SAN].strip(),
            as_int(fields[J_MAIN]),
            as_int(fields[J_SUB]),
        )
    return table


def load_extra(path: Path) -> dict[str, tuple[str, str, str, int]]:
    """Map 관리번호 to administrative district, building name, and housing flag."""

    table: dict[str, tuple[str, str, str, int]] = {}
    for fields in iter_pipe_rows(path, EXTRA_FIELDS):
        mgmt = fields[X_MGMT].strip()
        name = fields[X_SGG_NAME].strip() or fields[X_LEDGER_NAME].strip()
        table[mgmt] = (
            fields[X_HDONG_CODE].strip(),
            fields[X_HDONG].strip(),
            name,
            as_int(fields[X_APARTMENT]),
        )
    return table


def normalized_listing(directory: Path) -> dict[str, Path]:
    """Map NFC-normalized file names to real paths.

    macOS stores Korean file names in NFD, so a glob written in NFC (as source
    code normally is) silently matches nothing. Normalizing both sides makes the
    lookup work on every filesystem.
    """

    listing: dict[str, Path] = {}
    for entry in directory.iterdir():
        if entry.is_file():
            listing[unicodedata.normalize("NFC", entry.name)] = entry
    return listing


def build_index(
    *,
    address_dir: Path | str,
    db_path: Path | str,
    english_dir: Path | str | None = None,
    progress: object = None,
) -> BuildReport:
    """Index the 주소DB (and optionally the 영문주소DB) into a SQLite lookup database."""

    address_dir = Path(address_dir)
    db_path = Path(db_path)
    listing = normalized_listing(address_dir)
    road_code_path = listing.get("개선_도로명코드_전체분.txt")
    if road_code_path is None:
        raise FileNotFoundError(f"개선_도로명코드_전체분.txt not found under {address_dir}")
    address_names = sorted(
        name for name in listing if name.startswith("주소_") and name.endswith(".txt")
    )
    if not address_names:
        raise FileNotFoundError(f"no 주소_*.txt found under {address_dir}")

    road_codes = load_road_codes(road_code_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    connection = sqlite3.connect(db_path)
    try:
        connection.executescript("PRAGMA journal_mode=OFF; PRAGMA synchronous=OFF;")
        connection.executescript(SCHEMA)

        address_rows = jibun_rows = extra_rows = unresolved = 0
        for name in address_names:
            path = listing[name]
            region = name[len("주소_"):-len(".txt")]
            jibun_path = listing.get(f"지번_{region}.txt")
            extra_path = listing.get(f"부가정보_{region}.txt")
            if jibun_path is None or extra_path is None:
                raise FileNotFoundError(f"지번/부가정보 file missing for region {region}")
            jibun = load_representative_jibun(jibun_path)
            extra = load_extra(extra_path)
            jibun_rows += len(jibun)
            extra_rows += len(extra)

            batch: list[tuple] = []
            for fields in iter_pipe_rows(path, ADDRESS_FIELDS):
                mgmt = fields[A_MGMT].strip()
                road_code = fields[A_ROAD_CODE].strip()
                emd_seq = fields[A_EMD_SEQ].strip()
                names = road_codes.get((road_code, emd_seq)) or road_codes.get((road_code, "00"))
                if not mgmt or names is None:
                    unresolved += 1
                    continue
                sido, sgg, emd, road, _road_en = names
                ldong_code, jibun_emd, jibun_ri, san, jibun_main, jibun_sub = jibun.get(
                    mgmt, ("", "", "", "", 0, 0)
                )
                hdong_code, hdong, bld_name, apartment = extra.get(mgmt, ("", "", "", 0))
                batch.append(
                    (
                        mgmt,
                        road_code,
                        emd_seq,
                        sido,
                        sgg,
                        emd,
                        road,
                        compact(road),
                        as_int(fields[A_UNDERGROUND]),
                        as_int(fields[A_BLD_MAIN]),
                        as_int(fields[A_BLD_SUB]),
                        fields[A_ZIP].strip(),
                        as_int(fields[A_DETAIL_FLAG]),
                        ldong_code,
                        jibun_emd,
                        jibun_ri,
                        san,
                        jibun_main,
                        jibun_sub,
                        hdong_code,
                        hdong,
                        bld_name,
                        apartment,
                        region,
                    )
                )
                if len(batch) >= INSERT_BATCH:
                    connection.executemany(
                        "INSERT INTO building VALUES (" + ",".join("?" * 24) + ")", batch
                    )
                    address_rows += len(batch)
                    batch.clear()
            if batch:
                connection.executemany(
                    "INSERT INTO building VALUES (" + ",".join("?" * 24) + ")", batch
                )
                address_rows += len(batch)
            connection.commit()
            if callable(progress):
                progress(f"{region} addresses={address_rows}")

        english_rows = 0
        if english_dir:
            english_listing = normalized_listing(Path(english_dir))
            english_names = sorted(
                n for n in english_listing if n.startswith("rn_") and n.endswith(".txt")
            )
            for path in (english_listing[n] for n in english_names):
                batch = []
                for fields in iter_pipe_rows(path, ENGLISH_FIELDS):
                    mgmt = fields[E_MGMT].strip()
                    if not mgmt:
                        continue
                    batch.append(
                        (
                            mgmt,
                            fields[E_SIDO_EN].strip(),
                            fields[E_SGG_EN].strip(),
                            fields[E_EMD_EN].strip(),
                            fields[E_ROAD_EN].strip(),
                        )
                    )
                    if len(batch) >= INSERT_BATCH:
                        connection.executemany("INSERT INTO english VALUES (?,?,?,?,?)", batch)
                        english_rows += len(batch)
                        batch.clear()
                if batch:
                    connection.executemany("INSERT INTO english VALUES (?,?,?,?,?)", batch)
                    english_rows += len(batch)
                connection.commit()
                if callable(progress):
                    progress(f"english {path.name} rows={english_rows}")

        connection.executescript(INDEXES)
        distinct_keys = connection.execute(
            "SELECT COUNT(DISTINCT mgmt_no) FROM building"
        ).fetchone()[0]
        sido = tuple(
            row[0] for row in connection.execute("SELECT DISTINCT sido FROM building ORDER BY sido")
        )
        for key, value in (
            ("address_rows", str(address_rows)),
            ("english_rows", str(english_rows)),
            ("regions", str(len(address_names))),
            ("road_codes", str(len(road_codes))),
            ("evidence_source", BULK_EVIDENCE_SOURCE),
            ("address_key_field", "주소DB 관리번호 (25) == Juso API bdMgtSn"),
        ):
            connection.execute("INSERT OR REPLACE INTO build_meta VALUES (?,?)", (key, value))
        connection.commit()
    finally:
        connection.close()

    return BuildReport(
        db_path=str(db_path),
        regions=len(address_names),
        address_rows=address_rows,
        jibun_rows=jibun_rows,
        extra_rows=extra_rows,
        english_rows=english_rows,
        road_codes=len(road_codes),
        unresolved_road_code=unresolved,
        distinct_keys=distinct_keys,
        distinct_sido=sido,
    )


def road_address_of(row: sqlite3.Row) -> str:
    parts = [row["sido"], row["sgg"]]
    if row["emd"].endswith(("읍", "면")):
        parts.append(row["emd"])
    parts.append(row["road"])
    number = ("지하 " if row["underground"] else "") + str(row["bld_main"])
    if row["bld_sub"]:
        number += f"-{row['bld_sub']}"
    parts.append(number)
    return " ".join(part for part in parts if part)


def jibun_address_of(row: sqlite3.Row) -> str:
    if not row["jibun_emd"] and not row["jibun_main"]:
        return ""
    parts = [row["sido"], row["sgg"], row["jibun_emd"]]
    if row["jibun_ri"]:
        parts.append(row["jibun_ri"])
    if row["san"] == "1":
        parts.append("산")
    number = str(row["jibun_main"])
    if row["jibun_sub"]:
        number += f"-{row['jibun_sub']}"
    parts.append(number)
    return " ".join(part for part in parts if part)


def english_address_of(row: sqlite3.Row) -> str:
    if not row["eng_road"]:
        return ""
    number = ("Jiha " if row["underground"] else "") + str(row["bld_main"])
    if row["bld_sub"]:
        number += f"-{row['bld_sub']}"
    segments = [number, row["eng_road"]]
    if row["eng_emd"] and row["eng_emd"].endswith(("-eup", "-myeon")):
        segments.append(row["eng_emd"])
    segments.extend(part for part in (row["eng_sgg"], row["eng_sido"]) if part)
    return ", ".join(segments)


def candidate_of(row: sqlite3.Row) -> Candidate:
    return Candidate(
        road_address=road_address_of(row),
        jibun_address=jibun_address_of(row),
        building_management_number=row["mgmt_no"],
        english_address=english_address_of(row),
        postal_code=row["zip"],
        administrative_code=row["ldong_code"],
        road_management_number=row["road_code"],
        building_name=row["bld_name"],
        detailed_building_names="",
    )


SELECT_COLUMNS = """
    b.mgmt_no, b.road_code, b.sido, b.sgg, b.emd, b.road, b.underground,
    b.bld_main, b.bld_sub, b.zip, b.detail_flag, b.ldong_code,
    b.jibun_emd, b.jibun_ri, b.san, b.jibun_main, b.jibun_sub,
    b.bld_name, b.apartment,
    e.sido AS eng_sido, e.sgg AS eng_sgg, e.emd AS eng_emd, e.road AS eng_road
"""


class BulkSearchClient:
    """Offline ``SearchClient`` over the indexed bulk address datasets."""

    evidence_source = BULK_EVIDENCE_SOURCE

    def __init__(self, db_path: Path | str, *, limit: int = DEFAULT_LIMIT):
        self._connection = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        self._connection.row_factory = sqlite3.Row
        self._limit = limit

    def close(self) -> None:
        self._connection.close()

    def __enter__(self) -> BulkSearchClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def _query(self, where: str, params: tuple) -> list[sqlite3.Row]:
        sql = (
            f"SELECT {SELECT_COLUMNS} FROM building AS b "
            "LEFT JOIN english AS e ON e.mgmt_no = b.mgmt_no "
            f"WHERE {where} LIMIT 200"
        )
        return list(self._connection.execute(sql, params))

    def search(self, keyword: str) -> list[Candidate]:
        rows: list[sqlite3.Row] = []
        road = parse_road_query(keyword)
        if road:
            rows = self._query(
                "b.road_norm = ? AND b.bld_main = ? AND b.bld_sub = ? AND b.underground = ?",
                (road.road_norm, road.bld_main, road.bld_sub, road.underground),
            )
        if not rows:
            jibun = parse_jibun_query(keyword)
            if jibun:
                rows = self._query(
                    "b.jibun_emd = ? AND b.jibun_main = ? AND b.jibun_sub = ?",
                    (jibun.emd, jibun.jibun_main, jibun.jibun_sub),
                )
        if not rows:
            return []

        rows = self._narrow_by_region(keyword, rows)
        seen: set[str] = set()
        candidates: list[Candidate] = []
        for row in rows:
            if row["mgmt_no"] in seen:
                continue
            seen.add(row["mgmt_no"])
            candidates.append(candidate_of(row))
            if len(candidates) >= self._limit:
                break
        return candidates

    @staticmethod
    def _narrow_by_region(keyword: str, rows: list[sqlite3.Row]) -> list[sqlite3.Row]:
        """Keep rows whose region names appear in the query, mirroring keyword search.

        The filter is applied only when it does not empty the result, so an
        incomplete query still yields candidates instead of a false unmatched.
        """

        normalized = compact(keyword)
        for field in ("sgg", "sido"):
            narrowed = [row for row in rows if row[field] and compact(row[field]) in normalized]
            if narrowed:
                rows = narrowed
        return rows
