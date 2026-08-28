# Juso Key · 주소키

[![CI](https://github.com/oswarld/adress/actions/workflows/ci.yml/badge.svg)](https://github.com/oswarld/adress/actions/workflows/ci.yml)
[![MIT License](https://img.shields.io/badge/license-MIT-0f766e.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-3776ab.svg)](https://www.python.org/)
[![MCP](https://img.shields.io/badge/protocol-MCP-6d28d9.svg)](https://modelcontextprotocol.io/)

> 매번 주소와 우편번호, 영문주소를 찾기 위해 광고 범벅인 웹사이트를 돌아다니셨나요? 이제 인공지능에서 쉽게 주소를 관리하세요.

주소키는 기관마다 제각각 적혀 있는 주소와 장소 정보를 하나의 공식 기준으로 확인하고 연결해 주는 서비스입니다. 새로운 번호를 만드는 것이 아니라 건물관리번호 등 이미 정부가 관리하는 공식 번호를 활용합니다. 주소가 바뀐 경우에는 변경 이력을 찾아 기존 자료를 자동으로 정리하고, 확인이 어려운 주소는 임의로 판단하지 않고 담당자가 검토하도록 구분합니다. AI도 장소를 추측해서 답하는 대신 공식 주소정보를 먼저 확인한 뒤, 근거가 있는 내용만 안내하게 됩니다. 사업체·관광지·의료시설 데이터를 대상으로 8주간 시범 운영하여 정확도와 오류 발생 여부, 담당자의 업무시간 절감 효과를 확인한 후 확대 여부를 결정합니다.

**[전수자료 검증 웹페이지 보기](https://oswarld.github.io/adress/)**

## 국민이 겪는 세 장면

### 1. 같은 장소인데 매번 다시 증명한다

사업장을 이전한 소상공인의 주소는 사업자 서류, 인허가 정보, 지원사업 신청서와 지도 노출에 서로 다르게 남습니다. 담당자는 같은 장소인지 확인하려 다시 연락하고, 사업자는 같은 서류를 반복 제출합니다. 표기 차이와 실제 장소 차이를 시스템이 구분하지 못하기 때문입니다. 공공데이터 300건 대조에서 후보로 보류된 67건이 바로 이 확인 작업이 필요한 상태였습니다.

### 2. 행정구역이 바뀌면 과거와 현재가 끊긴다

가령 광주광역시와 전라남도가 전남광주통합특별시로 통합되면서 그 지역 723,357건의 주소 문자열이 바뀌었습니다. 통합 이전에 수집된 데이터의 주소는 이제 공식 문자열과 일치하지 않으므로 자동 확정 대상에서 탈락합니다. 안내 발송, 이력 조회, 시점별 통계의 대상이 엇갈리고 이용자는 어느 기관 정보가 아직 과거 주소인지 알기 어렵습니다. 반면 그 건물들의 주소키는 그대로입니다. 연결 수단을 문자열에서 주소키로 옮기면 이 단절을 막을 수 있습니다.

### 3. AI가 엉뚱한 장소를 자신 있게 답한다

이용자가 AI 챗봇이나 에이전트에게 특정 시설을 물으면 AI는 여러 데이터의 주소 문자열을 유사도로 결합합니다. 공식 검증 절차가 없으면 후보가 둘이어도 하나를 골라 말할 수 있고, 틀렸을 때 무엇을 근거로 답했는지 남지 않습니다.

> 첫 번째와 두 번째 장면의 구조적 원인은 전수자료 대조로 확인했습니다. 다만 그로 인한 국민의 시간·비용 손실 규모는 아직 측정하지 않았습니다. 세 번째 장면은 시범에서 검증할 개선 가설입니다. 사용자 보완 횟수, 잘못된 결합 건수, 근거 없는 AI 단정 건수를 측정하기 전에는 효과를 수치로 주장하지 않습니다.

## 전수자료로 확인한 출발점

2026년 7월 31일 기준 공식 주소DB 전체분을 로컬 인덱스로 구축해 동일한 판정 규칙으로 감사했습니다.

| 확인한 사실 | 결과 |
|---|---:|
| 주소·25자리 관리번호 | 6,422,308건 · 전부 유일 |
| 서로 다른 도로명주소 문자열 | 6,422,308건 |
| 복수 건물을 가리키는 공식 문자열 | 0건 |
| 공공데이터 300건 자동 확정 | 195건 (65.0%, 주소 공란 제외 71.7%) |
| 후보 / 미매칭 / 원본 공란 | 67 / 10 / 28건 |
| 확정이 아닌 상태에서 키 출력 | 0건 |

공식 주소 문자열은 현재 배포본에서 건물과 1:1입니다. 문제는 실제 공공데이터의 표기가 공식 문자열과 어긋나고, 행정구역 개편 때 문자열이 바뀌어 과거 연결이 끊긴다는 점입니다. 전체 6,422,308건 중 1,544,141건(24.04%)은 현재 시도와 다른 개편 전 코드의 관리번호를 유지했습니다. Juso Key는 이 안정적인 키를 공식 근거와 함께 전달하되, 약한 일치에서는 키를 숨깁니다.

## 무엇을 할 수 있나요?

| 요청 | 결과 |
|---|---|
| “서울시청 주소와 우편번호 알려줘” | 공식 도로명·지번주소와 우편번호 |
| “이 주소를 영문으로 써줘” | 공식 검색 결과의 영문주소 |
| “두 주소가 같은 건물이야?” | 양쪽의 공식 건물관리번호가 확인된 경우에만 동일성 판정 |
| 불완전하거나 중복되는 주소 | 후보만 제시하고 사용자 확인 요청 |

이 프로젝트에는 광고·분석 SDK나 질의 이력 수집기가 없습니다. 기본 API 모드에서는 조회할 주소가 [주소기반산업지원서비스](https://business.juso.go.kr/)의 공식 Juso API로 전송됩니다. 선택형 오프라인 모드는 사용자가 직접 내려받은 공식 전체분과 로컬 SQLite 인덱스만 사용하며 질의를 외부로 보내지 않습니다.

## 빠른 시작: API 모드

Python 3.11 이상, [uv](https://docs.astral.sh/uv/), 공식 주소검색 API 승인키가 필요합니다.

```bash
git clone https://github.com/oswarld/adress.git
cd adress/plugins/juso-key
uv sync --locked
export JUSO_API_KEY="발급받은_승인키"
uv run juso-key verify "서울특별시 중구 세종대로 110"
```

## 승인키 없는 오프라인 모드

[주소기반산업지원서비스](https://business.juso.go.kr/)에서 `주소DB 전체분`과 선택적으로 `영문주소DB 전체분`을 내려받은 뒤 로컬 인덱스를 만듭니다. 원본 파일과 SQLite 인덱스는 저장소에 커밋하지 않습니다.

```bash
cd adress/plugins/juso-key
uv run juso-key build-index \
  --address-dir "/path/to/202607_주소DB_전체분" \
  --english-dir "/path/to/202607_영문주소DB_전체분" \
  --out "$PWD/juso_bulk.sqlite"

uv run juso-key verify --offline \
  --index "$PWD/juso_bulk.sqlite" \
  "서울특별시 중구 세종대로 110"
```

MCP에서도 `JUSO_BULK_INDEX=/absolute/path/juso_bulk.sqlite`를 설정하면 로컬 인덱스를 우선 사용합니다. 이 값이 없을 때만 `JUSO_API_KEY`를 사용합니다. 응답의 `evidence.source`가 실제 조회 경로를 명시합니다.

## AI 클라이언트에 설치하기

### Claude Code

```text
/plugin marketplace add oswarld/adress
/plugin install juso-key@juso-key-plugins
```

로컬 개발 중이라면 저장소 루트에서 다음처럼 바로 실행할 수 있습니다.

```bash
export JUSO_API_KEY="발급받은_승인키"
claude --plugin-dir ./plugins/juso-key
```

### Codex

저장소를 복제한 뒤 로컬 저장소형 마켓플레이스를 등록합니다.

```bash
codex plugin marketplace add /absolute/path/to/adress
codex plugin add juso-key@juso-key-plugins
```

MCP 서버만 직접 등록할 수도 있습니다.

```bash
codex mcp add juso-key \
  --env JUSO_API_KEY="$JUSO_API_KEY" \
  -- uv run --project "$PWD/plugins/juso-key" juso-key-mcp
```

### ChatGPT 웹·원격 MCP 클라이언트

원격 클라이언트에는 HTTPS Streamable HTTP 엔드포인트가 필요합니다. 제공된 Dockerfile은 `/health`와 bearer 인증이 적용된 `/mcp`를 실행합니다.

```bash
cd plugins/juso-key
docker build -t juso-key .
docker run --rm -p 8000:8000 \
  -e JUSO_API_KEY="발급받은_승인키" \
  -e MCP_BEARER_TOKEN="충분히_긴_무작위_토큰" \
  -e MCP_ALLOWED_HOSTS="localhost:*,127.0.0.1:*" \
  juso-key
```

공개 배포에서는 TLS를 적용하고 실제 호스트만 허용하세요. 자세한 절차는 [배포·제출 체크리스트](docs/SUBMISSION.md)를 참고하세요.

## AI가 받는 안전한 계약

```json
{
  "matchStatus": "confirmed",
  "assertable": true,
  "addressKeyType": "BD_MGT_SN",
  "addressKey": "official-value-only",
  "evidence": {
    "officialRoadAddress": "서울특별시 중구 세종대로 110",
    "officialJibunAddress": "서울특별시 중구 태평로1가 31",
    "officialEnglishAddress": "110, Sejong-daero, Jung-gu, Seoul",
    "postalCode": "04524",
    "matchMethod": "exact_road",
    "scoreType": "deterministic_rule_score_not_probability"
  }
}
```

| 상태 | `assertable` | AI가 해야 할 일 |
|---|---:|---|
| `confirmed` | `true` | 공식 결과를 근거와 함께 제시 |
| `candidate` | `false` | 키를 숨기고 후보 중 선택 요청 |
| `unmatched` | `false` | 일치 결과가 없다고 알리고 추측 금지 |

## 프로젝트 구조

```text
.agents/plugins/marketplace.json  Codex 저장소형 마켓플레이스
.claude-plugin/marketplace.json   Claude Code 마켓플레이스
plugins/juso-key/
├── .claude-plugin/plugin.json    Claude 플러그인 매니페스트
├── .codex-plugin/plugin.json     Codex 플러그인 매니페스트
├── .mcp.json                     로컬 stdio MCP 설정
├── skills/                       공급자 중립 Agent Skill
├── src/juso_key/bulk.py          주소DB 전체분 로컬 인덱서
├── src/juso_key/                 결정론적 판정기와 MCP 서버
└── tests/                        계약·파서·전송·오프라인 회귀 테스트
```

## 개발과 검증

```bash
cd plugins/juso-key
uv sync --locked --all-groups
uv run pytest
uv run ruff check .
```

현재 자동테스트는 24건이며, 주소DB 관리번호가 API의 `bdMgtSn`과 같은 25자리 값인지와 행정구역 옛 표기에서 주소키를 자동 출력하지 않는지까지 검사합니다.

기여 방법은 [CONTRIBUTING.md](CONTRIBUTING.md), 개인정보 처리 방식은 [PRIVACY.md](PRIVACY.md), 보안 신고는 [SECURITY.md](SECURITY.md)를 확인하세요.

## 한계

- 건물관리번호는 건물 단위 주소 객체를 식별하며 사람·사업체·동·층·호를 식별하지 않습니다.
- 좌표 조회와 지오코딩을 제공하지 않습니다.
- 주소를 영구 저장하거나 주소록을 운영하지 않습니다.
- 전체분 인덱스는 공식 원본을 재배포하지 않으며, 사용자가 내려받은 파일로 로컬에서 직접 구축해야 합니다.
- 고위험 의사결정이나 법적 제출 전에는 사람이 공식 결과를 다시 확인해야 합니다.

## 라이선스

Juso Key는 [MIT License](LICENSE)로 배포됩니다.
