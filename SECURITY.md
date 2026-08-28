# Security policy

## Sensitive data

Juso Key sends the address supplied to `verify_korean_address` to the official Juso search API unless `JUSO_BULK_INDEX` configures a local full-release index. It does not intentionally persist queries or API responses. Operators must avoid request-body logging and should minimize retention in reverse proxies and observability systems.

Never commit `JUSO_API_KEY`, `MCP_BEARER_TOKEN`, generated SQLite indexes, downloaded full-release datasets, real private residential addresses, or raw production exports. Use environment variables or a secret manager, and mount local indexes read-only for remote deployments.

## Remote deployment

The bundled HTTP entry point refuses MCP traffic unless `MCP_BEARER_TOKEN` is configured. Set `MCP_ALLOWED_HOSTS` to the exact public host and terminate TLS at a trusted reverse proxy or hosting platform. Rotate the MCP bearer token and Juso API key if either may have been exposed. If using `JUSO_BULK_INDEX`, restrict file permissions to the service account and do not expose the SQLite file as a downloadable asset.

## Reporting a vulnerability

Open a private GitHub security advisory in the repository that distributes this plugin. Do not include live credentials, private addresses, or unredacted request logs in a public issue.
