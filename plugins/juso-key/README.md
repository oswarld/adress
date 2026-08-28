# Juso Key plugin

> 매번 주소와 우편번호, 영문주소를 찾기 위해 광고 범벅인 웹사이트를 돌아다니셨나요? 이제 인공지능에서 쉽게 주소를 관리하세요.

Juso Key exposes the read-only `verify_korean_address` MCP tool and a provider-neutral Agent Skill. It returns official Korean road-name and land-lot addresses, postal codes, English addresses, and a conservative building-level match contract. It can use either the live Juso search API or a local index built from the official full-release address dataset.

The 2026-07 full release contained 6,422,308 unique 25-character management numbers and 6,422,308 unique rendered road-name address strings, with no string mapping to multiple buildings. Applying the unchanged resolver to a fixed 300-row public-data sample confirmed 195 rows, held 67 as candidates, left 10 unmatched, and found 28 empty source addresses. No non-confirmed result exposed an address key.

See the [repository README](../../README.md) for client installation and the [submission checklist](../../docs/SUBMISSION.md) for remote deployment.

## Requirements

- Python 3.11 or newer
- [uv](https://docs.astral.sh/uv/)
- Either a search API approval key or official full-release address files from [주소기반산업지원서비스](https://business.juso.go.kr/)

The approval key is separate from a general data.go.kr service key.

## Install and test

```bash
uv sync --locked --all-groups
export JUSO_API_KEY="your-approval-key"
uv run pytest
uv run ruff check .
uv run juso-key verify "서울특별시 중구 세종대로 110"
```

Build and query a local index without an approval key:

```bash
uv run juso-key build-index \
  --address-dir "/path/to/202607_주소DB_전체분" \
  --english-dir "/path/to/202607_영문주소DB_전체분" \
  --out "$PWD/juso_bulk.sqlite"
uv run juso-key verify --offline --index "$PWD/juso_bulk.sqlite" \
  "서울특별시 중구 세종대로 110"
```

Set `JUSO_BULK_INDEX` to that SQLite path to make the MCP server use the local index. If the variable is absent, the server uses `JUSO_API_KEY`. `evidence.source` always identifies the actual source.

Inspect the MCP server with:

```bash
uv run mcp dev src/juso_key/server.py
```

## Tool contract

Input:

```json
{
  "address": "서울특별시 중구 세종대로 110"
}
```

Important output fields:

```json
{
  "matchStatus": "confirmed",
  "assertable": true,
  "addressKeyType": "BD_MGT_SN",
  "addressKey": "official-value-only",
  "responseDirective": "may_assert_official_match",
  "evidence": {
    "officialRoadAddress": "서울특별시 중구 세종대로 110",
    "officialJibunAddress": "서울특별시 중구 태평로1가 31",
    "officialEnglishAddress": "110, Sejong-daero, Jung-gu, Seoul",
    "postalCode": "04524",
    "source": "Juso search API",
    "matchMethod": "exact_road",
    "scoreType": "deterministic_rule_score_not_probability"
  }
}
```

`addressKey` is null for `candidate` and `unmatched`. Candidate previews intentionally omit every building management number so a model cannot convert an ambiguous result into a false assertion.

## Remote MCP

The Dockerfile runs an authenticated Streamable HTTP server with `/health` and `/mcp` endpoints.

```bash
docker build -t juso-key .
docker run --rm -p 8000:8000 \
  -e JUSO_API_KEY="your-approval-key" \
  -e MCP_BEARER_TOKEN="use-a-long-random-secret" \
  -e MCP_ALLOWED_HOSTS="localhost:*,127.0.0.1:*" \
  juso-key
```

For a private deployment that must keep queries local, mount the index read-only and set `JUSO_BULK_INDEX` instead of `JUSO_API_KEY`.

Terminate TLS at the deployment platform or a trusted reverse proxy. Never expose an unauthenticated MCP endpoint, and disable request-body logging wherever address text could be captured.

## Decision boundaries

- Only exact or conservatively normalized top candidates sharing one non-empty `bdMgtSn` can be confirmed.
- Containment and token similarity rank candidates but never confirm an address key.
- Comparing two spellings requires two confirmed, assertable results with equal non-empty keys.
- Floor and room suffixes may be removed for building-level comparison, but the unit itself is not verified.
- A superseded province name may produce one strong candidate but must remain non-assertable until the current official string is confirmed. Administrative reorganization does not imply that an existing management number changed.
- The server performs no generative matching and stores no address history.

## License

[MIT](LICENSE)
