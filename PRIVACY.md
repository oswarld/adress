# Privacy policy

Effective date: 2026-08-28

Juso Key is an open-source address lookup and verification tool. This policy describes the behavior of the software in this repository. A third party that hosts or modifies Juso Key may operate under additional terms.

## Data processed

When a user invokes `verify_korean_address`, the software uses one of two operator-configured sources. With `JUSO_BULK_INDEX`, it reads a local SQLite index built from the official full-release address files and does not send the query to the Juso API. Without that setting, the supplied Korean address is sent to the official Juso search API operated through Korea's address information service. The response may contain official road-name and land-lot addresses, a postal code, an English address, and a building management number. The response's `evidence.source` identifies which path was used.

## Storage and retention

Juso Key includes an optional builder for a local SQLite index of official full-release data. That index contains official address records, not query history. The software includes no analytics SDK, advertising SDK, or address-history feature and does not intentionally persist address queries or API responses. A hosting provider, reverse proxy, MCP client, or observability service may create logs independently; operators should disable request-body logging and minimize retention.

## Credentials

API keys, local index paths, and MCP bearer tokens are read from environment variables. Credentials, downloaded full-release files, and generated SQLite indexes must not be committed to source control or exposed to clients.

## Sharing

In API mode, address queries are shared with the official Juso search API only as required to perform the lookup. In local-index mode, queries are not sent to that API. Juso Key does not sell address data or share it with advertisers.

## Contact

Open a GitHub issue at <https://github.com/oswarld/adress/issues> for privacy questions. Do not include a private residential address, credentials, or raw request logs in a public issue. Report security issues through a private GitHub security advisory as described in [SECURITY.md](SECURITY.md).
