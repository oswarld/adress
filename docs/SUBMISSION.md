# Distribution and submission checklist

## Included in this repository

- Provider-neutral Agent Skill at `plugins/juso-key/skills/verify-korean-address/`
- Local stdio and authenticated Streamable HTTP MCP transports
- Claude Code plugin and repository marketplace manifests
- Codex plugin and repository marketplace manifests
- MIT license, privacy policy, terms, security policy, CI, and tests
- Python wheel and source-distribution configuration

## Before the first public release

- [ ] Review every file listed by `git status --short`.
- [ ] Confirm no API key, bearer token, private address, participant record, or raw log is present.
- [ ] Run `uv run pytest` and `uv run ruff check .` from `plugins/juso-key`.
- [ ] Run the Agent Skill and Claude/Codex plugin validators.
- [ ] Push to `https://github.com/oswarld/adress` and confirm GitHub Actions passes.
- [ ] Add the repository description and topics: `mcp`, `agent-skill`, `korean-address`, `postal-code`, `claude`, `chatgpt`, `codex`.
- [ ] Create a signed or annotated `v0.2.0` tag and a GitHub release after review.

## Remote connector submission

- [ ] Deploy `plugins/juso-key/Dockerfile` behind HTTPS.
- [ ] Choose one evidence source: set `JUSO_API_KEY`, or mount a locally built index read-only and set `JUSO_BULK_INDEX`.
- [ ] Set `MCP_BEARER_TOKEN` and exact `MCP_ALLOWED_HOSTS` values as secrets.
- [ ] Disable request-body logging at the proxy and application-monitoring layers.
- [ ] Verify `GET /health`, authenticated `POST /mcp`, host filtering, and TLS.
- [ ] Register the resulting `https://<host>/mcp` endpoint in the target AI client.
- [ ] Add a product-specific `.app.json` only after the target platform issues its application ID; IDs are deployment- and account-specific and must not be invented in the repository.
- [ ] Use the public URLs for [privacy](../PRIVACY.md), [terms](../TERMS.md), and [security](../SECURITY.md) during submission.

## Known release boundary

The plugin looks up and verifies addresses; it does not maintain a persistent address book, provide coordinates, or geocode results. The optional SQLite file is an operator-built index of official full-release data, not a query-history store, and must not be committed or bundled. Marketing text should use “manage addresses in AI” as a convenience message, not as a claim that Juso Key stores user queries.
