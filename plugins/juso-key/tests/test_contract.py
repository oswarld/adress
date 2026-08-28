from juso_key.contract import verify_address_with_client
from juso_key.resolver import Candidate


class FakeClient:
    def __init__(self, candidates: list[Candidate]):
        self.candidates = candidates

    def search(self, keyword: str) -> list[Candidate]:
        return self.candidates


def candidate(
    road: str,
    key: str,
    postal_code: str = "04524",
    english_address: str = "110, Sejong-daero, Jung-gu, Seoul",
) -> Candidate:
    return Candidate(
        road_address=road,
        jibun_address="",
        building_management_number=key,
        english_address=english_address,
        postal_code=postal_code,
    )


def test_confirmed_key_is_assertable():
    result = verify_address_with_client(
        "서울특별시 중구 세종대로 110",
        FakeClient([candidate("서울특별시 중구 세종대로 110", "TEST-BD-001")]),
    )
    assert result["assertable"] is True
    assert result["addressKey"] == "TEST-BD-001"
    assert result["responseDirective"] == "may_assert_official_match"
    assert result["evidence"]["postalCode"] == "04524"
    assert result["evidence"]["officialEnglishAddress"] == (
        "110, Sejong-daero, Jung-gu, Seoul"
    )


def test_candidate_withholds_every_key_but_presents_addresses():
    result = verify_address_with_client(
        "중앙로 10",
        FakeClient(
            [
                candidate("테스트시 가구 중앙로 10", "TEST-BD-101"),
                candidate("테스트시 나구 중앙로 10", "TEST-BD-102"),
            ]
        ),
    )
    assert result["assertable"] is False
    assert result["addressKey"] is None
    assert len(result["candidates"]) == 2
    assert "addressKey" not in result["candidates"][0]


def test_unmatched_instructs_model_not_to_invent():
    result = verify_address_with_client("없는 주소 999", FakeClient([]))
    assert result["matchStatus"] == "unmatched"
    assert result["assertable"] is False
    assert result["responseDirective"] == "state_no_official_match_and_do_not_invent"


def test_empty_and_control_character_inputs_are_rejected_before_search():
    client = FakeClient([])
    for value in ("", "서울\n중구"):
        try:
            verify_address_with_client(value, client)
        except ValueError:
            pass
        else:
            raise AssertionError(f"expected input rejection: {value!r}")
