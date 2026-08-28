"""Deterministic matching against candidates returned by the official Juso API."""

from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

JUSO_ENDPOINT = "https://business.juso.go.kr/addrlink/addrLinkApi.do"
USER_AGENT = "JusoKey/0.1"
DEFAULT_TIMEOUT_SECONDS = 20
MAX_RETRIES = 3
MAX_ADDRESS_LENGTH = 300


@dataclass(frozen=True)
class Candidate:
    road_address: str
    jibun_address: str
    building_management_number: str
    english_address: str = ""
    postal_code: str = ""
    administrative_code: str = ""
    road_management_number: str = ""
    building_name: str = ""
    detailed_building_names: str = ""


@dataclass(frozen=True)
class ScoredCandidate:
    candidate: Candidate
    score: float
    method: str


@dataclass(frozen=True)
class Resolution:
    raw_address: str
    query_address: str
    address_key_type: str
    address_key: str
    official_road_address: str
    official_jibun_address: str
    official_english_address: str
    postal_code: str
    match_status: str
    match_method: str
    match_confidence: float
    candidate_count: int
    top_candidate_gap: float
    evidence_source: str
    source_fetched_at: str


class SearchClient(Protocol):
    def search(self, keyword: str) -> list[Candidate]: ...


def text(value: object) -> str:
    return "" if value is None else str(value).strip()


def validate_address_input(value: str) -> str:
    query = unicodedata.normalize("NFKC", value).strip()
    if not query:
        raise ValueError("address must not be empty")
    if len(query) > MAX_ADDRESS_LENGTH:
        raise ValueError(f"address must be at most {MAX_ADDRESS_LENGTH} characters")
    if any(unicodedata.category(char) in {"Cc", "Cs"} for char in query):
        raise ValueError("address contains unsupported control characters")
    return query


def compact(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[^0-9a-z가-힣]", "", value)


def without_parenthetical(value: str) -> str:
    return re.sub(r"\([^)]*\)", " ", value)


def without_likely_detail(value: str) -> str:
    """Remove only unambiguous floor or unit suffixes for building comparison."""

    cleaned = without_parenthetical(value)
    cleaned = re.sub(r"\s*,\s*", " ", cleaned)
    cleaned = re.sub(
        r"(?:\s|^)(?:지하\s*)?\d+\s*층(?:\s+\d+\s*호)?(?:\s|$)",
        " ",
        cleaned,
    )
    cleaned = re.sub(r"(?:\s|^)\d+\s*호(?:\s|$)", " ", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()


def variants(value: str) -> set[str]:
    return {
        normalized
        for normalized in (
            compact(value),
            compact(without_parenthetical(value)),
            compact(without_likely_detail(value)),
        )
        if normalized
    }


def token_set(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", without_parenthetical(value)).lower()
    return set(re.findall(r"[0-9a-z가-힣]+", normalized))


def score_against(query: str, official: str, kind: str) -> tuple[float, str]:
    if not query or not official:
        return 0.0, "none"
    query_variants = variants(query)
    official_variants = variants(official)
    if compact(query) == compact(official):
        return 1.0, f"exact_{kind}"
    if query_variants & official_variants:
        return 0.98, f"normalized_{kind}"

    containment = [
        min(len(left), len(right)) / max(len(left), len(right))
        for left in query_variants
        for right in official_variants
        if min(len(left), len(right)) >= 8 and (left in right or right in left)
    ]
    if containment:
        return min(0.94, 0.84 + 0.1 * max(containment)), f"contained_{kind}"

    query_tokens = token_set(query)
    official_tokens = token_set(official)
    if not query_tokens or not official_tokens:
        return 0.0, "none"
    intersection = len(query_tokens & official_tokens)
    union = len(query_tokens | official_tokens)
    jaccard = intersection / union
    if jaccard >= 0.5:
        return round(0.45 + 0.35 * jaccard, 4), f"token_{kind}"
    return 0.0, "none"


def score_candidate(query: str, candidate: Candidate) -> ScoredCandidate:
    road_score, road_method = score_against(query, candidate.road_address, "road")
    jibun_score, jibun_method = score_against(query, candidate.jibun_address, "jibun")
    if road_score >= jibun_score:
        return ScoredCandidate(candidate, road_score, road_method)
    return ScoredCandidate(candidate, jibun_score, jibun_method)


def rank_candidates(query: str, candidates: Iterable[Candidate]) -> list[ScoredCandidate]:
    return sorted(
        (score_candidate(query, candidate) for candidate in candidates),
        key=lambda item: (-item.score, item.candidate.building_management_number),
    )


DEFAULT_EVIDENCE_SOURCE = "Juso search API"


def resolve_candidates(
    *,
    raw_address: str,
    query_address: str,
    candidates: Iterable[Candidate],
    source_fetched_at: str,
    evidence_source: str = DEFAULT_EVIDENCE_SOURCE,
) -> Resolution:
    scored = rank_candidates(query_address, candidates)
    if not scored:
        return Resolution(
            raw_address=raw_address,
            query_address=query_address,
            address_key_type="BD_MGT_SN",
            address_key="",
            official_road_address="",
            official_jibun_address="",
            official_english_address="",
            postal_code="",
            match_status="unmatched",
            match_method="no_result",
            match_confidence=0.0,
            candidate_count=0,
            top_candidate_gap=0.0,
            evidence_source=evidence_source,
            source_fetched_at=source_fetched_at,
        )

    top = scored[0]
    second_score = scored[1].score if len(scored) > 1 else 0.0
    top_key = top.candidate.building_management_number
    tied_top = [item for item in scored if item.score == top.score]
    same_nonempty_key = bool(top_key) and all(
        item.candidate.building_management_number == top_key for item in tied_top
    )
    can_confirm = top.score >= 0.98 and same_nonempty_key

    return Resolution(
        raw_address=raw_address,
        query_address=query_address,
        address_key_type="BD_MGT_SN",
        address_key=top_key if can_confirm else "",
        official_road_address=top.candidate.road_address,
        official_jibun_address=top.candidate.jibun_address,
        official_english_address=top.candidate.english_address,
        postal_code=top.candidate.postal_code,
        match_status="confirmed" if can_confirm else "candidate",
        match_method=top.method if top.score else "unranked_candidate",
        match_confidence=round(top.score, 4),
        candidate_count=len(scored),
        top_candidate_gap=round(top.score - second_score, 4),
        evidence_source=evidence_source,
        source_fetched_at=source_fetched_at,
    )


class JusoSearchClient:
    def __init__(self, approval_key: str, *, timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS):
        if not approval_key.strip():
            raise ValueError("Juso API approval key is required")
        self._approval_key = approval_key.strip()
        self._timeout_seconds = timeout_seconds

    def search(self, keyword: str) -> list[Candidate]:
        params = {
            "confmKey": self._approval_key,
            "currentPage": 1,
            "countPerPage": 10,
            "keyword": validate_address_input(keyword),
            "resultType": "json",
            "hstryYn": "Y",
        }
        request = urllib.request.Request(
            JUSO_ENDPOINT + "?" + urllib.parse.urlencode(params),
            headers={"Accept": "application/json", "User-Agent": USER_AGENT},
        )
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                with urllib.request.urlopen(request, timeout=self._timeout_seconds) as response:
                    payload = json.loads(response.read().decode("utf-8"))
                return self._parse(payload)
            except (
                urllib.error.URLError,
                urllib.error.HTTPError,
                TimeoutError,
                json.JSONDecodeError,
            ) as error:
                last_error = error
                if attempt + 1 < MAX_RETRIES:
                    time.sleep(0.5 * (2**attempt))
        raise RuntimeError("Juso search API request failed after retries") from last_error

    @staticmethod
    def _parse(payload: dict[str, object]) -> list[Candidate]:
        results = payload.get("results")
        if not isinstance(results, dict):
            raise RuntimeError("Juso response is missing results")
        common = results.get("common")
        if not isinstance(common, dict):
            raise RuntimeError("Juso response is missing common metadata")
        error_code = text(common.get("errorCode"))
        if error_code != "0":
            message = text(common.get("errorMessage"))
            raise RuntimeError(f"Juso API error {error_code}: {message}")

        raw_candidates = results.get("juso") or []
        if isinstance(raw_candidates, dict):
            raw_candidates = [raw_candidates]
        if not isinstance(raw_candidates, list):
            return []

        candidates: list[Candidate] = []
        for item in raw_candidates:
            if not isinstance(item, dict):
                continue
            candidates.append(
                Candidate(
                    road_address=text(item.get("roadAddr")),
                    jibun_address=text(item.get("jibunAddr")),
                    building_management_number=text(item.get("bdMgtSn")),
                    english_address=text(item.get("engAddr")),
                    postal_code=text(item.get("zipNo")),
                    administrative_code=text(item.get("admCd")),
                    road_management_number=text(item.get("rnMgtSn")),
                    building_name=text(item.get("bdNm")),
                    detailed_building_names=text(item.get("detBdNmList")),
                )
            )
        return candidates
