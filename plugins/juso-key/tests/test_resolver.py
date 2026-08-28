from juso_key.resolver import Candidate, JusoSearchClient, resolve_candidates


def candidate(road: str, key: str, jibun: str = "", english: str = "") -> Candidate:
    return Candidate(
        road_address=road,
        jibun_address=jibun,
        building_management_number=key,
        english_address=english,
    )


def resolve(address: str, candidates: list[Candidate]):
    return resolve_candidates(
        raw_address=address,
        query_address=address,
        candidates=candidates,
        source_fetched_at="2026-08-28T00:00:00+00:00",
    )


def test_exact_match_is_confirmed():
    result = resolve(
        "서울특별시 중구 세종대로 110",
        [candidate("서울특별시 중구 세종대로 110", "TEST-BD-001")],
    )
    assert result.match_status == "confirmed"
    assert result.address_key == "TEST-BD-001"
    assert result.match_confidence == 1.0


def test_floor_detail_can_normalize_to_same_building():
    result = resolve(
        "서울특별시 중구 세종대로 110, 3층",
        [candidate("서울특별시 중구 세종대로 110", "TEST-BD-001")],
    )
    assert result.match_status == "confirmed"
    assert result.match_method == "normalized_road"


def test_tied_exact_candidates_with_different_keys_are_not_confirmed():
    result = resolve(
        "중앙로 10",
        [
            candidate("중앙로 10", "TEST-BD-101"),
            candidate("중앙로 10", "TEST-BD-102"),
        ],
    )
    assert result.match_status == "candidate"
    assert result.address_key == ""


def test_tied_candidate_with_missing_key_is_not_confirmed():
    result = resolve(
        "중앙로 10",
        [candidate("중앙로 10", "TEST-BD-101"), candidate("중앙로 10", "")],
    )
    assert result.match_status == "candidate"
    assert result.address_key == ""


def test_no_candidates_is_unmatched():
    result = resolve("없는 주소 999", [])
    assert result.match_status == "unmatched"
    assert result.candidate_count == 0


def test_parser_rejects_api_error_without_exposing_request_url():
    try:
        JusoSearchClient._parse(
            {
                "results": {
                    "common": {"errorCode": "E0006", "errorMessage": "승인되지 않은 KEY"},
                    "juso": None,
                }
            }
        )
    except RuntimeError as error:
        assert "E0006" in str(error)
        assert "confmKey" not in str(error)
    else:
        raise AssertionError("expected a Juso API error")


def test_parser_preserves_official_postal_and_english_addresses():
    candidates = JusoSearchClient._parse(
        {
            "results": {
                "common": {"errorCode": "0", "errorMessage": "정상"},
                "juso": [
                    {
                        "roadAddr": "서울특별시 중구 세종대로 110",
                        "jibunAddr": "서울특별시 중구 태평로1가 31",
                        "engAddr": "110, Sejong-daero, Jung-gu, Seoul",
                        "zipNo": "04524",
                        "bdMgtSn": "TEST-BD-001",
                    }
                ],
            }
        }
    )
    assert candidates[0].postal_code == "04524"
    assert candidates[0].english_address == "110, Sejong-daero, Jung-gu, Seoul"
