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

## Consequences

- Python 3.10 environments can no longer install scan-namer.
- Forced by SDK 2.x rather than chosen: `AnthropicClient` no longer sends
  `temperature`; `llm.temperature` / `LLM_TEMPERATURE` still apply to the
  other providers.
- Claude requests sample at the model's default temperature (1.0) instead
  of the configured value (default 0.3).
