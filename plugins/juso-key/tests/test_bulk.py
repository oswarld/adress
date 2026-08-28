"""Offline bulk-index tests.

The fixtures are written in the same CP949 pipe-separated form as the official
주소DB full-release files, so the encoding and positional layout are exercised
rather than assumed. Keys are 25-character 관리번호 values, matching what the
search API returns as ``bdMgtSn``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from juso_key.bulk import (
    BULK_EVIDENCE_SOURCE,
    BulkSearchClient,
    build_index,
    parse_road_query,
)
from juso_key.resolver import resolve_candidates

FETCHED_AT = "2026-08-28T00:00:00+09:00"


def pipe(count: int, **values: str) -> str:
    fields = [""] * count
    for position, value in values.items():
        fields[int(position[1:])] = value
    return "|".join(fields)


def road_code_row(*, code: str, road: str, road_en: str, emd_seq: str,
                  sido: str, sido_en: str, sgg: str, sgg_en: str, emd: str = "") -> str:
    return pipe(17, f0=code, f1=road, f2=road_en, f3=emd_seq,
                f4=sido, f5=sido_en, f6=sgg, f7=sgg_en, f8=emd)


def address_row(*, mgmt: str, code: str, emd_seq: str, bld_main: int,
                bld_sub: int = 0, underground: int = 0, zip_code: str = "00000",
                detail_flag: int = 0) -> str:
    return pipe(11, f0=mgmt, f1=code, f2=emd_seq, f3=str(underground),
                f4=str(bld_main), f5=str(bld_sub), f6=zip_code, f10=str(detail_flag))


def jibun_row(*, mgmt: str, ldong: str, sido: str, sgg: str, emd: str,
              main: int, sub: int = 0, representative: str = "1") -> str:
    return pipe(11, f0=mgmt, f1="1", f2=ldong, f3=sido, f4=sgg, f5=emd,
                f7="0", f8=str(main), f9=str(sub), f10=representative)


def extra_row(*, mgmt: str, hdong_code: str, hdong: str, zip_code: str,
              name: str = "", apartment: str = "0") -> str:
    return pipe(9, f0=mgmt, f1=hdong_code, f2=hdong, f3=zip_code,
                f7=name, f8=apartment)


def english_row(*, mgmt: str, sido: str, sgg: str, emd: str, road: str) -> str:
    return pipe(18, f1=sido, f2=sgg, f3=emd, f9=road, f13=mgmt)


SEOUL_KEY = "1114010300100310000000001"
CHUNCHEON_KEY = "5111010100100010000000001"
UNDERGROUND_KEY = "1111010100101440003031291"

SEJONG_DAERO = "111402005001"
CHUNCHEON_ROAD = "511103218033"
JAHAMUN_RO = "111103100012"


@pytest.fixture
def index(tmp_path: Path) -> Path:
    address_dir = tmp_path / "juso"
    english_dir = tmp_path / "eng"
    address_dir.mkdir()
    english_dir.mkdir()

    def write(path: Path, lines: list[str]) -> None:
        path.write_text("\r\n".join(lines) + "\r\n", encoding="cp949")

    write(
        address_dir / "개선_도로명코드_전체분.txt",
        [
            road_code_row(code=SEJONG_DAERO, road="세종대로", road_en="Sejong-daero",
                          emd_seq="01", sido="서울특별시", sido_en="Seoul",
                          sgg="중구", sgg_en="Jung-gu", emd="태평로1가"),
            road_code_row(code=CHUNCHEON_ROAD, road="중앙로", road_en="Jungang-ro",
                          emd_seq="01", sido="강원특별자치도", sido_en="Gangwon-do",
                          sgg="춘천시", sgg_en="Chuncheon-si", emd="봉의동"),
            road_code_row(code=JAHAMUN_RO, road="자하문로", road_en="Jahamun-ro",
                          emd_seq="01", sido="서울특별시", sido_en="Seoul",
                          sgg="종로구", sgg_en="Jongno-gu", emd="청운동"),
        ],
    )
    write(
        address_dir / "주소_테스트.txt",
        [
            address_row(mgmt=SEOUL_KEY, code=SEJONG_DAERO, emd_seq="01",
                        bld_main=110, zip_code="04524", detail_flag=1),
            address_row(mgmt=CHUNCHEON_KEY, code=CHUNCHEON_ROAD, emd_seq="01",
                        bld_main=1, zip_code="24266"),
            address_row(mgmt=UNDERGROUND_KEY, code=JAHAMUN_RO, emd_seq="01",
                        bld_main=94, underground=1, zip_code="03047"),
        ],
    )
    write(
        address_dir / "지번_테스트.txt",
        [
            jibun_row(mgmt=SEOUL_KEY, ldong="1114010300", sido="서울특별시",
                      sgg="중구", emd="태평로1가", main=31),
            jibun_row(mgmt=CHUNCHEON_KEY, ldong="5111010100", sido="강원특별자치도",
                      sgg="춘천시", emd="봉의동", main=1),
            jibun_row(mgmt=UNDERGROUND_KEY, ldong="1111010100", sido="서울특별시",
                      sgg="종로구", emd="청운동", main=144, sub=3),
        ],
    )
    write(
        address_dir / "부가정보_테스트.txt",
        [
            extra_row(mgmt=SEOUL_KEY, hdong_code="1114055000", hdong="소공동",
                      zip_code="04524", name="서울특별시청"),
            extra_row(mgmt=CHUNCHEON_KEY, hdong_code="5111051000", hdong="교동",
                      zip_code="24266"),
            extra_row(mgmt=UNDERGROUND_KEY, hdong_code="1111051500",
                      hdong="청운효자동", zip_code="03047"),
        ],
    )
    write(
        english_dir / "rn_test.txt",
        [
            english_row(mgmt=SEOUL_KEY, sido="Seoul", sgg="Jung-gu",
                        emd="Taepyeongno 1(il)-ga", road="Sejong-daero")
        ],
    )

    db_path = tmp_path / "index.sqlite"
    report = build_index(
        address_dir=address_dir, english_dir=english_dir, db_path=db_path
    )
    assert report.address_rows == 3
    assert report.english_rows == 1
    assert report.distinct_keys == 3
    assert report.unresolved_road_code == 0
    assert report.road_codes == 3
    return db_path


def resolve(client: BulkSearchClient, query: str):
    return resolve_candidates(
        raw_address=query,
        query_address=query,
        candidates=client.search(query),
        source_fetched_at=FETCHED_AT,
        evidence_source=BULK_EVIDENCE_SOURCE,
    )


def test_parse_road_query_handles_underground_and_sub_numbers() -> None:
    plain = parse_road_query("서울특별시 중구 세종대로 110")
    assert plain is not None
    assert (plain.bld_main, plain.bld_sub, plain.underground) == (110, 0, 0)

    underground = parse_road_query("서울특별시 종로구 자하문로 지하 94")
    assert underground is not None
    assert (underground.bld_main, underground.underground) == (94, 1)

    sub = parse_road_query("서울특별시 종로구 자하문로 96-3")
    assert sub is not None
    assert (sub.bld_main, sub.bld_sub) == (96, 3)

    numbered_road = parse_road_query("경상남도 창원시 진해구 제덕로234번길 12")
    assert numbered_road is not None
    assert numbered_road.road == "제덕로234번길"
    assert numbered_road.bld_main == 12

    assert parse_road_query("서울특별시 중구") is None


def test_exact_official_string_is_confirmed_with_key(index: Path) -> None:
    with BulkSearchClient(index) as client:
        resolution = resolve(client, "서울특별시 중구 세종대로 110")
    assert resolution.match_status == "confirmed"
    assert resolution.address_key == SEOUL_KEY
    assert resolution.match_method == "exact_road"
    assert resolution.postal_code == "04524"
    assert resolution.official_jibun_address == "서울특별시 중구 태평로1가 31"
    assert resolution.official_english_address.startswith("110, Sejong-daero")
    assert resolution.evidence_source == BULK_EVIDENCE_SOURCE


def test_detail_suffix_still_confirms_the_building(index: Path) -> None:
    with BulkSearchClient(index) as client:
        resolution = resolve(client, "서울특별시 중구 세종대로 110, 3층 301호")
    assert resolution.match_status == "confirmed"
    assert resolution.address_key == SEOUL_KEY


def test_superseded_region_name_is_not_auto_confirmed(index: Path) -> None:
    """강원도 → 강원특별자치도 style renames must not silently auto-confirm.

    The building is the same and the road and building number match, but the
    stored region name no longer matches the official string. The contract
    requires a candidate with no key rather than a confirmed match.
    """

    with BulkSearchClient(index) as client:
        legacy = resolve(client, "강원도 춘천시 중앙로 1")
        current = resolve(client, "강원특별자치도 춘천시 중앙로 1")

    assert legacy.match_status == "candidate"
    assert legacy.address_key == ""
    assert legacy.official_road_address == "강원특별자치도 춘천시 중앙로 1"
    assert legacy.match_confidence < 0.98

    assert current.match_status == "confirmed"
    assert current.address_key == CHUNCHEON_KEY


def test_underground_number_does_not_collide_with_ground_level(index: Path) -> None:
    with BulkSearchClient(index) as client:
        underground = resolve(client, "서울특별시 종로구 자하문로 지하 94")
        ground = resolve(client, "서울특별시 종로구 자하문로 94")
    assert underground.address_key == UNDERGROUND_KEY
    assert ground.match_status == "unmatched"


def test_address_key_is_a_25_character_management_number(index: Path) -> None:
    """The key must be the 주소DB 관리번호, which is what the API returns."""

    with BulkSearchClient(index) as client:
        resolution = resolve(client, "서울특별시 중구 세종대로 110")
    assert len(resolution.address_key) == 25
    assert resolution.address_key.isdigit()


def test_unknown_address_returns_unmatched_without_key(index: Path) -> None:
    with BulkSearchClient(index) as client:
        resolution = resolve(client, "서울특별시 중구 없는길 9999")
    assert resolution.match_status == "unmatched"
    assert resolution.address_key == ""
    assert resolution.candidate_count == 0


def test_missing_index_file_is_reported(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        build_index(address_dir=tmp_path, db_path=tmp_path / "x.sqlite")
