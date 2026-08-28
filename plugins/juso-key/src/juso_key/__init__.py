"""Juso Key: AI-safe verification for South Korean addresses."""

from .bulk import BulkSearchClient, build_index
from .contract import build_verification_response, verify_address_with_client
from .resolver import Candidate, JusoSearchClient, Resolution, resolve_candidates

__all__ = [
    "Candidate",
    "BulkSearchClient",
    "JusoSearchClient",
    "Resolution",
    "build_verification_response",
    "build_index",
    "resolve_candidates",
    "verify_address_with_client",
]

__version__ = "0.2.0"
