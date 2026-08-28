"""Model-facing verification contract built from deterministic resolver output."""

from __future__ import annotations

from datetime import UTC, datetime

from .resolver import (
    DEFAULT_EVIDENCE_SOURCE,
    Candidate,
    JusoSearchClient,
    Resolution,
    SearchClient,
    rank_candidates,
    resolve_candidates,
    validate_address_input,
)

DIRECTIVES = {
    "confirmed": "may_assert_official_match",
    "candidate": "present_candidates_and_request_confirmation",
    "unmatched": "state_no_official_match_and_do_not_invent",
}


def utc_timestamp() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def candidate_previews(query: str, candidates: list[Candidate], *, limit: int = 5) -> list[dict]:
    previews: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in rank_candidates(query, candidates):
        key = (
            item.candidate.road_address,
            item.candidate.jibun_address,
            item.candidate.english_address,
            item.candidate.postal_code,
        )
        if key in seen:
            continue
        seen.add(key)
        previews.append(
            {
                "officialRoadAddress": item.candidate.road_address or None,
                "officialJibunAddress": item.candidate.jibun_address or None,
                "officialEnglishAddress": item.candidate.english_address or None,
                "postalCode": item.candidate.postal_code or None,
                "matchMethod": item.method,
                "score": round(item.score, 4),
            }
        )
        if len(previews) >= limit:
            break
    return previews


def build_verification_response(
    resolution: Resolution,
    *,
    candidates: list[Candidate],
    ruleset_version: str = "1.0.0",
) -> dict[str, object]:
    if resolution.match_status not in DIRECTIVES:
        raise ValueError(f"unsupported match status: {resolution.match_status}")

    assertable = resolution.match_status == "confirmed" and bool(resolution.address_key)
    return {
        "query": resolution.raw_address,
        "matchStatus": resolution.match_status,
        "assertable": assertable,
        "addressKeyType": resolution.address_key_type,
        "addressKey": resolution.address_key if assertable else None,
        "responseDirective": DIRECTIVES[resolution.match_status],
        "evidence": {
            "source": resolution.evidence_source,
            "officialRoadAddress": resolution.official_road_address or None,
            "officialJibunAddress": resolution.official_jibun_address or None,
            "officialEnglishAddress": resolution.official_english_address or None,
            "postalCode": resolution.postal_code or None,
            "candidateCount": resolution.candidate_count,
            "matchMethod": resolution.match_method,
            "score": resolution.match_confidence,
            "scoreType": "deterministic_rule_score_not_probability",
            "topCandidateGap": resolution.top_candidate_gap,
            "sourceFetchedAt": resolution.source_fetched_at,
        },
        "candidates": (
            candidate_previews(resolution.query_address, candidates)
            if resolution.match_status == "candidate"
            else []
        ),
        "decision": {
            "authority": "official_address_data_plus_deterministic_rules",
            "rulesetVersion": ruleset_version,
            "modelAssistUsed": False,
            "modelRole": "not_used",
        },
        "limitations": [
            "BD_MGT_SN is a building-level address identifier, not a person or business ID.",
            (
                "This result does not verify apartment units, floors, rooms, coordinates, "
                "or occupancy."
            ),
            "The score is deterministic and is not a calibrated probability.",
        ],
    }


def verify_address_with_client(address: str, client: SearchClient) -> dict[str, object]:
    """Verify one address through any SearchClient.

    A client may declare its own ``evidence_source`` so the response never
    attributes an offline lookup to the live search API.
    """

    query = validate_address_input(address)
    fetched_at = utc_timestamp()
    candidates = client.search(query)
    resolution = resolve_candidates(
        raw_address=query,
        query_address=query,
        candidates=candidates,
        source_fetched_at=fetched_at,
        evidence_source=getattr(client, "evidence_source", DEFAULT_EVIDENCE_SOURCE),
    )
    return build_verification_response(resolution, candidates=candidates)


def verify_live_address(address: str, approval_key: str) -> dict[str, object]:
    return verify_address_with_client(address, JusoSearchClient(approval_key))
