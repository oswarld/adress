# Verification contract

`verify_korean_address` returns these decision fields:

- `matchStatus`: `confirmed`, `candidate`, or `unmatched`.
- `assertable`: true only when a unique official candidate has a non-empty building management number and the query exactly or conservatively normalizes to the official address.
- `addressKeyType`: currently `BD_MGT_SN`.
- `addressKey`: present only when `assertable` is true; otherwise null.
- `responseDirective`: the required model behavior for the status.
- `evidence`: official Korean road and land-lot address text, postal code, English address, match method, deterministic score, candidate count, and fetch time.
- `candidates`: address, postal code, and English-address previews for disambiguation. Candidate building management numbers are intentionally withheld.
- `limitations`: boundaries that must accompany high-impact uses.

The score is rule-based and is not a calibrated probability. Token or containment matches can rank candidates but cannot produce `confirmed` status.

`evidence.source` is authoritative for provenance. `Juso search API` means the query was sent to the official API. `Juso bulk dataset (주소DB full release)` means it was resolved against a local index built from the downloaded full release. Do not describe one source as the other.

`BD_MGT_SN` is the 25-character 관리번호 from the 주소DB and the same identifier returned by the API. The 26-character first field in `rnaddrkor_*.txt` is a different identifier and must not be substituted. Existing management numbers normally retain their original legal-district prefix through an administrative reorganization; never recalculate or synthesize them from a current region code.

For a same-building comparison, call the tool once per input. Equality is assertable only when both calls return `confirmed`, both return `assertable=true`, and their non-empty `addressKey` values are equal.
