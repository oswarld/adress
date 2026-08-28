---
name: verify-korean-address
description: Find and verify a South Korean road-name or land-lot address against the official Juso API or a local full-release index. Use for official Korean addresses, postal codes, English addresses, building management numbers, or safe comparison of two Korean address spellings. Do not use for non-Korean addresses, coordinates, or geocoding.
---

# Verify Korean Address

Use the `verify_korean_address` MCP tool for the address the user supplied. Do not claim the plugin stores an address book.

Report the evidence source from `evidence.source` rather than assuming one. The default deployment sends the address to the official Juso search API, so do not claim the check stayed entirely local. A deployment configured against a downloaded full-release dataset resolves the address locally instead, and `evidence.source` names that dataset; in that case do not claim the address was sent to the API.

Interpret the tool response as a decision contract:

- `confirmed` and `assertable=true`: report the requested official road or land-lot address, postal code, English address, and building management number when present. Briefly state the match method.
- `candidate` and `assertable=false`: do not expose, infer, or invent an address key. Present the returned address candidates and ask the user to disambiguate.
- `unmatched` and `assertable=false`: say that no official match was found. Ask for a fuller road-name or land-lot address; do not repair it by guessing.
- Tool or configuration error: explain that verification could not be completed. Do not substitute a model-generated answer.

Treat `evidence.score` as a deterministic comparison score, not a probability. A building management number identifies a building-level address object; it does not uniquely identify a person, business, apartment unit, floor, or room.

A `candidate` result whose returned official address differs from the user's input only in the province or metropolitan-city name is the expected outcome for a superseded administrative name, not a tool failure. Korean province names change: 강원도 became 강원특별자치도, 전라북도 became 전북특별자치도, and the 2026-07 official dataset publishes 광주광역시 and 전라남도 addresses under 전남광주통합특별시. Present the current official candidate, explain the region-name difference, and ask the user to confirm. Do not emit or infer an address key from the candidate.

Existing 25-character building management numbers retain the legal-district code assigned when they were created; an administrative reorganization does not itself rewrite those identifiers. New buildings may receive the new code. Never synthesize a management number from either the old or current region code, and never use this stability rule to bypass `assertable=false`.

The audited 2026-07 full release contained 6,422,308 unique rendered road-name address strings for 6,422,308 building records, with zero strings mapping to multiple buildings. This supports deterministic lookup from an exact current official string, but it does not relax the response contract: real source data can be incomplete or non-current, so containment and token matches remain candidates without keys.

When comparing two address spellings, verify each separately. Say they refer to the same building only when both results are `confirmed`, both are `assertable=true`, and both non-empty `addressKey` values are equal. Otherwise, present the unresolved evidence without concluding that they are the same.

Keep private addresses out of persistent notes, files, logs, and unrelated output. Return only the evidence needed for the user's request.

For the complete field contract when debugging an integration, read [references/contract.md](references/contract.md).
