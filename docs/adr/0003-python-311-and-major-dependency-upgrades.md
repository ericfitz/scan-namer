# ADR 0003: Require Python 3.11 and move to Pillow 13, websockets 17 and anthropic 2

- Status: Accepted
- Date: 2026-10-25
- Decision maker: Eric Fitzgerald (human decision)

## Context

Pillow 12.3.0 has CRITICAL, HIGH and MEDIUM advisories (Dependabot and
pip-audit) whose only fixed release is 13.0.0, and Pillow 13 requires
Python 3.11. websockets 17 (pulled in by google-genai) also requires 3.11.
The project declared `requires-python = ">=3.10"`, which blocked both.

anthropic SDK 2.x uses API version 2026-10-21, which rejects `temperature`,
`top_p` and `top_k` on Messages requests; the SDK no longer accepts them.

## Decision

- `requires-python` is `>=3.11` (also the PEP 723 header of
  `update_models.py`). Ruff's target follows it.
- Dependencies are `Pillow>=13.0.0` and `anthropic>=2.3.0`; the lock moves
  websockets to 17.
- No provider request sets `temperature`, `top_p` or `top_k`: every model
  samples at its own default. The `llm.temperature` / `LLM_TEMPERATURE`
  setting is removed; a leftover value logs a warning and is ignored.

## Consequences

- Python 3.10 environments can no longer install scan-namer.
- Requests that used the configured temperature (default 0.3) now use each
  model's default, which is often 1.0, so suggested names may vary more
  between runs.
