# LM Studio Provider Support

## Problem

Running `scan-namer` with LM Studio configured as the provider fails immediately:

```
2026-04-27T04:52:18.584Z - ERROR - No client implementation for provider: lmstudio
```

The `LLMClientFactory.create_client` method in [scan_namer.py:1518](../../../scan_namer.py#L1518) dispatches on `provider` with branches for `xai`, `anthropic`, `openai`, and `google`. There is no `lmstudio` branch, so the call falls through to a `sys.exit(1)`.

`config.json` already declares an `lmstudio` provider with endpoint `http://localhost:1234/v1/chat/completions` and two available models (`google/gemma-4-31b`, `qwen/qwen3.6-35b-a3b`), both flagged `vision_support: true` and `pdf_support: false`.

## Goal

Make `--provider lmstudio` work end-to-end against a locally running LM Studio instance, with no new third-party dependencies.

Out of scope: adopting `litellm` as a unified abstraction layer; migrating existing provider clients; adding other local backends (Ollama, vLLM).

## Approach

LM Studio exposes an OpenAI-compatible `/v1/chat/completions` endpoint. The existing `OpenAIClient` already implements every code path we need: text-mode chat completions and vision-mode rasterized-PNG uploads using the standard `image_url` content blocks. The official `openai` Python SDK accepts a `base_url` parameter for non-OpenAI endpoints.

The fix is therefore a thin subclass that overrides only what's different.

## Design

### New class: `LMStudioClient(OpenAIClient)`

Placed in [scan_namer.py](../../../scan_namer.py) immediately after `OpenAIClient`.

**Overrides:**

1. **`_get_api_key`** — LM Studio does not require authentication. If the env var named by `llm.providers.lmstudio.api_key_env` (default `LMSTUDIO_API_KEY`) is set and non-empty, use it. Otherwise return the placeholder string `"lm-studio"`. Never call `sys.exit(1)` for a missing key.

2. **`_setup_client`** — Read `llm.providers.lmstudio.api_endpoint` from config. If it ends with `/chat/completions`, strip that suffix to obtain the base URL the `openai` SDK expects (e.g. `http://localhost:1234/v1`). Instantiate `openai.OpenAI(api_key=self.api_key, base_url=<derived_base>)`.

**Inherited unchanged:**

- `analyze_document` — handles text-mode and the `supports_pdf()` / `supports_vision()` branching.
- `_analyze_via_rasterized_pages` — rasterizes the first N pages to PNG and posts them as `image_url` content blocks. This is the path LM Studio's vision models will use, since `pdf_support` is `false` for both configured models.

### Factory wiring

Add a single branch in `LLMClientFactory.create_client` around [scan_namer.py:1571](../../../scan_namer.py#L1571):

```python
elif provider == "lmstudio":
    return LMStudioClient(config, provider, model, max_tokens)
```

### Defensive token-usage handling

LM Studio responses may omit or zero out the `usage` field for some models. The `openai` SDK exposes `response.usage` — accessing `.prompt_tokens` etc. on a `None` usage object will raise `AttributeError`.

To prevent crashes, override `analyze_document` is **not** required if we instead add a small helper at the `OpenAIClient` level:

```python
def _extract_usage(self, response) -> Dict[str, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    return {
        "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
        "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
        "total_tokens": getattr(usage, "total_tokens", 0) or 0,
    }
```

Replace the two inline `cost_info = {...}` dict literals in `OpenAIClient.analyze_document` and `OpenAIClient._analyze_via_rasterized_pages` with `cost_info = self._extract_usage(response)`. This benefits both clients.

### Connection-error UX

The parent `OpenAIClient.analyze_document` already wraps the SDK call in `try/except Exception`, logs the error, and returns `(None, {})`. Don't override that. Instead, in `LMStudioClient._setup_client`, emit one INFO log line on startup showing the resolved base URL — e.g. `"LM Studio client initialized: base_url=http://localhost:1234/v1"`. Users who see "OpenAI API error: Connection refused" alongside this startup line will know exactly where to look.

### Config

No changes required — `config.json` already declares the provider, endpoint, models, and capability flags correctly.

### Documentation touch-ups

- **`.env.example`** — add a commented `LMSTUDIO_API_KEY=` line noting it is optional and only needed if running behind an authenticating proxy.
- **`CLAUDE.md`** — add LM Studio to the "Multi-LLM Integration" bullet list under *Key Integrations*.
- **`README.md`** — add LM Studio to the "Multi-provider LLM support" line at [README.md:12](../../../README.md#L12) (currently lists X.AI, Anthropic, OpenAI, Google).

## Testing

No automated test framework exists in this repo. Manual verification:

1. Start LM Studio with one of the configured models loaded and the local server enabled on port 1234.
2. `./scan-namer --provider lmstudio --dry-run --verbose` against a small test document.
3. Confirm the run completes without a "No client implementation" error and produces a suggested filename.
4. `./scan-namer --list-models` — confirm `lmstudio` appears with its two models.
5. Negative test: stop the LM Studio server, re-run, confirm the failure mode is a clean error rather than a stack trace.

## Risks

- **LM Studio model names contain slashes** (`google/gemma-4-31b`). The OpenAI SDK forwards the model string verbatim, and LM Studio accepts this format, so no special handling is needed. Documented here so it is not "discovered" mid-implementation.
- **Token usage may be zero** for some local models — handled by the `_extract_usage` helper above.
- **Vision model quality varies wildly** for local models. Out of scope; user-facing concern, not a code concern.

## Files Touched

- [scan_namer.py](../../../scan_namer.py) — add `LMStudioClient` class, `_extract_usage` helper on `OpenAIClient`, factory branch.
- [.env.example](../../../.env.example) — add optional `LMSTUDIO_API_KEY` entry.
- [CLAUDE.md](../../../CLAUDE.md) — add LM Studio to provider list.
- [README.md](../../../README.md) — add LM Studio to provider list at line 12.
