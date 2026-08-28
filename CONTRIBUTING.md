# Contributing

Contributions are welcome through GitHub issues and pull requests.

## Development

```bash
cd plugins/juso-key
uv sync --locked --all-groups
uv run pytest
uv run ruff check .
```

Run the Skill and plugin validators before opening a pull request:

```bash
python3 /path/to/skill-creator/scripts/quick_validate.py skills/verify-korean-address
python3 /path/to/plugin-creator/scripts/validate_plugin.py .
```

## Safety rules

- Never commit API keys, bearer tokens, real private residential addresses, or production logs.
- Use synthetic identifiers and public institutional addresses in fixtures and documentation.
- Preserve the fail-closed contract: ambiguous candidates must never expose an `addressKey`.
- Add tests for any change to matching, parsing, or model-facing response fields.

By contributing, you agree that your contribution is licensed under the repository's MIT License.

