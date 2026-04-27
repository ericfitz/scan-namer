# Update Models Script — Design

**Date:** 2026-04-26
**Status:** Approved (pending implementation plan)

## Purpose

Provide a standalone Python script that connects to each LLM provider listed in `config.json`, enumerates the models currently available to the caller, and rewrites that provider's `available_models` and `pdf_support` entries. Today these lists are maintained by hand and drift out of date as providers add/remove models.

The script is independent from `scan_namer.py` — it does not import from it and runs as its own command.

## Files

- `update_models.py` — main script with inline `uv` dependencies, sibling to `scan_namer.py`
- `update-models` — bash wrapper analogous to the existing `scan-namer` wrapper

## Config Changes

### Add `api_endpoint` to providers that lack one

Anthropic, OpenAI, and Google currently rely on SDK defaults. Add an explicit `api_endpoint` field for each so the per-provider header line ("Probing provider X at endpoint Y") has something concrete to print and so all providers are uniform.

Suggested values:

- Anthropic: `https://api.anthropic.com`
- OpenAI: `https://api.openai.com/v1`
- Google: `https://generativelanguage.googleapis.com` (Gen AI SDK default; Vertex AI uses a region-scoped URL)

### LiteLLM registry URL (script constant, not config)

```python
LITELLM_REGISTRY_URL = "https://raw.githubusercontent.com/BerriAI/litellm/main/model_prices_and_context_window.json"
```

The registry is a single JSON file maintained by the LiteLLM team. Each entry includes `supports_pdf_input`, `supports_vision`, and `litellm_provider`. We use it as the source of truth for capability metadata, replacing what would otherwise be brittle HTML scraping of each provider's docs page.

## API Key File Convention

API key files in the project root are named with the **uppercase** form of `api_key_env` (e.g., `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`). The existing files have already been renamed to match. The script reads the file first, then falls back to the environment variable, then attempts an anonymous request.

## CLI

```
./update-models                       # all providers, no probing
./update-models --provider anthropic  # one provider only
./update-models --enable-probing      # probe unknown models with a tiny PDF
./update-models --dry-run             # do not write config.json
./update-models --verbose             # debug logging
```

`--enable-probing` is **off by default**. Probing is reserved for unrecognized models (those not present in the LiteLLM registry).

## Per-Provider Flow

For each provider in `config.llm.providers` (or the single one passed via `--provider`):

### 1. Resolve credentials

1. Read file `<api_key_env>` from the project root (e.g., `ANTHROPIC_API_KEY`).
2. If absent, read `os.environ[api_key_env]`.
3. If still absent, proceed with no key (anonymous). Cloud providers will return 401 — that is the expected and reported failure mode.

### 2. Fetch LiteLLM registry (once per run)

Performed once at script start, cached for the duration of the run. Network failure → warn and treat the registry as empty (every model becomes "unknown"; behavior then depends on `--enable-probing`).

### 3. List models from the provider's API

Provider-specific call (see Provider-Specific Implementations below). Apply a per-provider filter to drop non-chat models (embeddings, TTS, image generation, transcription, deprecated). On failure, the provider's status is a red X; the script moves to the next provider.

### 4. For each API model

1. Look up in the LiteLLM registry by trying both the bare model id and the namespaced form `{provider}/{model_id}` (e.g., `xai/grok-4-0709`).
2. If found: use `supports_pdf_input` (None or missing → `false`).
3. Else if `--enable-probing`: send a tiny PDF probe (see Probe below); set `pdf_support` based on the result.
4. Else: include the model with `pdf_support: false`.
5. Print a per-model status line.

### 5. Write back

Replace the provider's `available_models` (sorted, deduplicated list of model ids) and rebuild `pdf_support` to contain exactly the models in `available_models`. Preserve `default_model` if it is still present in the new list; otherwise reset it to the first entry. Atomic write: stage to `config.json.tmp`, then rename.

## Provider-Specific Implementations

| Provider  | List models                                         | PDF probe                                                                      |
|-----------|-----------------------------------------------------|--------------------------------------------------------------------------------|
| LMStudio  | `GET {api_endpoint_root}/v1/models` (OpenAI-compat) | Chat completion with `image_url: data:application/pdf;base64,...`              |
| Anthropic | `client.models.list()`                              | `messages.create` with `document` content block, `media_type: application/pdf` |
| OpenAI    | `client.models.list()`, prefix-filter chat models   | `client.responses.create` with `input_file` content (or `chat.completions` with `image_url: data:application/pdf;base64,...` as currently used in `scan_namer.py`); implementation chooses what works |
| Google    | `client.models.list()` (google-genai SDK)           | `models.generate_content` with `inline_data` `application/pdf`                 |
| XAI       | `GET {api_endpoint_root}/v1/models`                 | Chat completion with `image_url: data:application/pdf;base64,...`              |

`api_endpoint_root` is derived by replacing the trailing `/chat/completions` in the configured `api_endpoint` with `/models`. Example: `http://localhost:1234/v1/chat/completions` → `http://localhost:1234/v1/models`.

### Model filters (chat-only)

- **OpenAI:** include ids that start with `gpt-` or `o`. Exclude embedding/whisper/tts/dall-e/moderation.
- **Anthropic:** include ids that start with `claude-`.
- **Google:** include ids that start with `gemini-`.
- **XAI:** include ids that start with `grok-`.
- **LMStudio:** include all (user-loaded models, no naming convention).

### PDF probe payload

A hardcoded base64-encoded minimal valid PDF (~few hundred bytes) embedded in the script. Probe call uses the smallest valid output token limit per provider (`max_tokens` for Anthropic/OpenAI chat-completions/XAI/LMStudio, `max_completion_tokens` for newer OpenAI Responses API, `max_output_tokens` for Google Gen AI) and a one-character user prompt (`.`).

Result interpretation:
- 2xx response → `pdf_support: true`
- 4xx whose error message indicates the model does not accept PDF/document/image input → `pdf_support: false`
- Any other error (auth, rate limit, network, server) → bubbled up as that model's error message; model is skipped from `available_models`

## Output Format

```
Probing provider anthropic at endpoint https://api.anthropic.com
    ✓  Model: claude-sonnet-4-20250514  [ Supports pdf: True ]
    ✓  Model: claude-3-5-haiku-20241022  [ Supports pdf: False ]
    ✗  Model: claude-foo-experimental  [ Error: HTTP 404 model not found ]
✅ anthropic  Model list updated

Probing provider xai at endpoint https://api.x.ai/v1/chat/completions
    ✗  Error: HTTP 401 unauthorized
❌ xai  Error retrieving list of models: HTTP 401 unauthorized
```

- Header line: `Probing provider {provider} at endpoint {endpoint}`
- Per-model line: `\t{✓|✗}  Model: {model_id}  [ Supports pdf: {bool} | Error: {msg} ]`
- Provider footer: `✅ {provider}  Model list updated` or `❌ {provider}  Error retrieving list of models: {msg}`

Per-model `✓` / `✗` use plain ASCII; per-provider summary uses ✅ / ❌. A per-model error does not block the provider — the failing model is simply omitted from the rebuilt lists.

## Error Handling Summary

| Failure                            | Behavior                                                                       |
|------------------------------------|--------------------------------------------------------------------------------|
| Missing provider section in config | Skip provider with red X                                                       |
| Registry fetch fails               | Warn; treat registry as empty (all models unknown → false unless probing)      |
| Provider API list call fails       | Red X for provider; no changes written for that provider                       |
| Per-model probe fails              | Model omitted from `available_models`                                          |
| `--dry-run`                        | Print exactly what would be written; do not touch `config.json`                |
| Write step                         | Atomic: stage to `config.json.tmp`, rename on success                          |

## Out of Scope

- Updating providers that are not currently in `config.json`.
- Inferring or updating `default_model` from anything other than "current default if still present, else first model in new list".
- Capabilities other than PDF support (vision-only, function calling, JSON mode, etc.). The registry has them; we just don't store them today.
- Pricing / context window data — registry has it but we do not import it.
