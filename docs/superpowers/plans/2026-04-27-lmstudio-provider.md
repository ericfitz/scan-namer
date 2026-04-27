# LM Studio Provider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `--provider lmstudio` work end-to-end against a locally running LM Studio instance, fixing the `No client implementation for provider: lmstudio` error.

**Architecture:** LM Studio speaks the OpenAI `/v1/chat/completions` schema natively. Add a thin `LMStudioClient` subclass of `OpenAIClient` that overrides only API-key handling (LM Studio doesn't require one) and SDK setup (uses `base_url` from config). Wire it into `LLMClientFactory`. Also harden `OpenAIClient`'s usage-extraction so missing/zero `usage` fields don't crash on local models.

**Tech Stack:** Python 3.8+, `openai` SDK (already a dependency), `uv` for inline-script dependency management. No new dependencies.

**Spec:** [docs/superpowers/specs/2026-04-27-lmstudio-provider-design.md](../specs/2026-04-27-lmstudio-provider-design.md)

**Note on testing:** This repo has no automated test framework — verification is via `python -c "import scan_namer"` (syntax/import check) and CLI smoke tests against the running script. Each task ends with such verification.

---

## File Structure

All code changes live in **one file**: [scan_namer.py](../../../scan_namer.py).

- **`OpenAIClient`** — gains a new `_extract_usage(response)` helper method; the two inline `cost_info = {...}` literals are replaced by calls to it.
- **`LMStudioClient(OpenAIClient)`** — new class added immediately after `OpenAIClient`.
- **`LLMClientFactory.create_client`** — gains one new `elif` branch.

Doc updates: [.env.example](../../../.env.example), [CLAUDE.md](../../../CLAUDE.md), [README.md](../../../README.md).

---

## Task 1: Add `_extract_usage` helper to `OpenAIClient`

This refactor stands on its own (defensive against zero/missing `usage` from any OpenAI-compatible server) and makes Task 2 cleaner.

**Files:**
- Modify: `scan_namer.py` — `OpenAIClient` class (add method ~line 1200, replace cost_info dicts at ~line 1239 and ~line 1321)

- [ ] **Step 1: Add the helper method**

In `scan_namer.py`, inside `class OpenAIClient(BaseLLMClient):`, immediately after the `_setup_client` method (the one ending at approximately line 1199), add this new method:

```python
    def _extract_usage(self, response: Any) -> Dict[str, int]:
        """Extract token usage from a chat-completions response.

        Defensive against missing/zero usage fields, which can happen with
        local OpenAI-compatible servers (e.g., LM Studio, llama.cpp).
        """
        usage = getattr(response, "usage", None)
        if usage is None:
            return {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        return {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }
```

- [ ] **Step 2: Replace inline usage extraction in `_analyze_via_rasterized_pages`**

Find this block in `OpenAIClient._analyze_via_rasterized_pages` (around line 1239):

```python
            cost_info = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            self.token_costs.append(cost_info)
```

Replace with:

```python
            cost_info = self._extract_usage(response)
            self.token_costs.append(cost_info)
```

- [ ] **Step 3: Replace inline usage extraction in `analyze_document`**

Find this block in `OpenAIClient.analyze_document` (around line 1321):

```python
            cost_info = {
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            }
            self.token_costs.append(cost_info)
```

Replace with:

```python
            cost_info = self._extract_usage(response)
            self.token_costs.append(cost_info)
```

- [ ] **Step 4: Verify the file still parses**

Run: `cd /Users/efitz/Projects/scan-namer && python -c "import ast; ast.parse(open('scan_namer.py').read()); print('OK')"`

Expected: prints `OK`. (Pure-Python AST parse — no dependencies needed, fast.)

- [ ] **Step 5: Smoke-test an existing provider to confirm no regression**

Run: `cd /Users/efitz/Projects/scan-namer && ./scan-namer --list-models 2>&1 | head -30`

Expected: provider list is printed, includes `openai`, no traceback. (No API call is made by `--list-models`, so this works even without an OpenAI key.)

- [ ] **Step 6: Commit**

```bash
cd /Users/efitz/Projects/scan-namer
git add scan_namer.py
git commit -m "$(cat <<'EOF'
refactor(openai): extract usage parsing into helper

Adds OpenAIClient._extract_usage to defensively handle missing or zero
token-usage fields from OpenAI-compatible servers (local backends like
LM Studio sometimes omit usage). Replaces two inline dict literals.
EOF
)"
```

---

## Task 2: Add `LMStudioClient` class

**Files:**
- Modify: `scan_namer.py` — insert new class immediately after `OpenAIClient` (before `class GoogleClient` at ~line 1338)

- [ ] **Step 1: Add the class**

In `scan_namer.py`, immediately after `OpenAIClient` ends (just before `class GoogleClient(BaseLLMClient):`), insert:

```python
class LMStudioClient(OpenAIClient):
    """LM Studio client.

    LM Studio exposes an OpenAI-compatible /v1/chat/completions endpoint at
    a user-configurable local URL. The `openai` Python SDK is reused with a
    custom `base_url`. No API key is required by LM Studio itself; if one is
    not configured we pass a placeholder string to satisfy the SDK.
    """

    def _get_api_key(self) -> str:
        """Return the configured API key, or a placeholder if unset.

        LM Studio does not authenticate by default. If the user has placed
        the local server behind an auth proxy, they can set the env var
        named by `llm.providers.lmstudio.api_key_env` (default
        LMSTUDIO_API_KEY); otherwise we return a non-empty placeholder so
        the openai SDK does not refuse to construct.
        """
        api_key_env = self.config.get(f"llm.providers.{self.provider}.api_key_env")
        if isinstance(api_key_env, str):
            api_key = os.getenv(api_key_env)
            if api_key:
                return api_key
        return "lm-studio"

    def _setup_client(self) -> None:
        """Set up the openai SDK pointed at the local LM Studio endpoint."""
        try:
            import openai
        except ImportError:
            logging.error(
                "OpenAI library not installed. Please install with: pip install openai"
            )
            sys.exit(1)

        endpoint = self.config.get(f"llm.providers.{self.provider}.api_endpoint")
        if not isinstance(endpoint, str) or not endpoint:
            logging.error(
                f"Invalid or missing api_endpoint for provider {self.provider}"
            )
            sys.exit(1)

        # The openai SDK expects the base URL (e.g. http://localhost:1234/v1),
        # not the full chat-completions URL. Strip the suffix if present.
        base_url = endpoint
        suffix = "/chat/completions"
        if base_url.endswith(suffix):
            base_url = base_url[: -len(suffix)]
        base_url = base_url.rstrip("/")

        self.client = openai.OpenAI(api_key=self.api_key, base_url=base_url)
        logging.info(f"LM Studio client initialized: base_url={base_url}")


```

(Note the trailing blank line — keep one blank line between the new class and `class GoogleClient`.)

- [ ] **Step 2: Verify the file still imports and parses**

Run: `cd /Users/efitz/Projects/scan-namer && python -c "import ast; ast.parse(open('scan_namer.py').read()); print('OK')"`

Expected: prints `OK`. (Pure-Python AST parse — no dependencies needed.)

- [ ] **Step 3: Verify the class is reachable but not yet wired**

Run: `cd /Users/efitz/Projects/scan-namer && ./scan-namer --provider lmstudio --dry-run 2>&1 | tail -5`

Expected: still shows `ERROR - No client implementation for provider: lmstudio` — that's correct, the factory wiring is Task 3. We just need the class itself to exist without breaking imports.

- [ ] **Step 4: Commit**

```bash
cd /Users/efitz/Projects/scan-namer
git add scan_namer.py
git commit -m "$(cat <<'EOF'
feat(lmstudio): add LMStudioClient subclassing OpenAIClient

LM Studio exposes the OpenAI /v1/chat/completions schema, so reuse the
existing OpenAI SDK path with a configurable base_url and an optional
API key (LM Studio does not authenticate by default). Class is added
but not yet wired into the factory.
EOF
)"
```

---

## Task 3: Wire up factory branch

**Files:**
- Modify: `scan_namer.py` — `LLMClientFactory.create_client`, add `elif` at ~line 1568

- [ ] **Step 1: Add the factory branch**

Find this block in `LLMClientFactory.create_client` (around line 1562):

```python
        # Create appropriate client
        if provider == "xai":
            return XAIClient(config, provider, model, max_tokens)
        elif provider == "anthropic":
            return AnthropicClient(config, provider, model, max_tokens)
        elif provider == "openai":
            return OpenAIClient(config, provider, model, max_tokens)
        elif provider == "google":
            return GoogleClient(config, provider, model, max_tokens)
        else:
            logging.error(f"No client implementation for provider: {provider}")
            sys.exit(1)
```

Replace with (single new `elif` for `lmstudio`, immediately before the `else`):

```python
        # Create appropriate client
        if provider == "xai":
            return XAIClient(config, provider, model, max_tokens)
        elif provider == "anthropic":
            return AnthropicClient(config, provider, model, max_tokens)
        elif provider == "openai":
            return OpenAIClient(config, provider, model, max_tokens)
        elif provider == "google":
            return GoogleClient(config, provider, model, max_tokens)
        elif provider == "lmstudio":
            return LMStudioClient(config, provider, model, max_tokens)
        else:
            logging.error(f"No client implementation for provider: {provider}")
            sys.exit(1)
```

- [ ] **Step 2: Verify the factory now dispatches**

Run: `cd /Users/efitz/Projects/scan-namer && ./scan-namer --provider lmstudio --list-models 2>&1 | tail -20`

Expected: a model list including `lmstudio` and its two models (`google/gemma-4-31b`, `qwen/qwen3.6-35b-a3b`). NO `No client implementation` error. (`--list-models` does not call the API, so this works without LM Studio running.)

- [ ] **Step 3: Smoke-test the dispatch path with `--dry-run`**

Run: `cd /Users/efitz/Projects/scan-namer && ./scan-namer --provider lmstudio --dry-run --verbose 2>&1 | tail -20`

Expected behavior depends on environment:

- **LM Studio running** with a configured model loaded: the script proceeds, lists Drive files, and (if any match the generic-name pattern) attempts a chat-completions call. Look for the `LM Studio client initialized: base_url=http://localhost:1234/v1` log line near the top.
- **LM Studio not running**: The script still gets past the factory and Drive listing, then fails on the actual API call with a connection-refused error from the `openai` SDK — NOT with the original `No client implementation` error.
- **No Google credentials**: the script may fail earlier at Drive auth. That is fine — the goal of this step is to confirm the factory dispatch path. Look for `LM Studio client initialized: ...` early in the log to confirm wiring.

If you see `No client implementation for provider: lmstudio` in the output, Task 3 Step 1 was not applied correctly — re-check the edit.

- [ ] **Step 4: Commit**

```bash
cd /Users/efitz/Projects/scan-namer
git add scan_namer.py
git commit -m "$(cat <<'EOF'
feat(lmstudio): wire LMStudioClient into LLMClientFactory

Closes the dispatch gap that produced 'No client implementation for
provider: lmstudio'.
EOF
)"
```

---

## Task 4: Documentation touch-ups

**Files:**
- Modify: `.env.example` — add `LMSTUDIO_API_KEY` line in the API CREDENTIALS section
- Modify: `CLAUDE.md` — add LM Studio to the Multi-LLM Integration list at line 79
- Modify: `README.md` — add LM Studio to the providers line at line 12

- [ ] **Step 1: Update `.env.example`**

In [.env.example](../../../.env.example), find this block (lines 19-21):

```
# Google Gemini API Key (get from https://aistudio.google.com/app/apikey)
# Required for PDF upload functionality with Gemini models
# GOOGLE_API_KEY=your_google_api_key_here
```

Immediately after the `# GOOGLE_API_KEY=...` line, append a blank line followed by:

```
# LM Studio API Key (optional - LM Studio does not authenticate by default;
# only set this if you have placed the LM Studio server behind an auth proxy)
# LMSTUDIO_API_KEY=any_string_works
```

Then in the same file, find this block (around line 30):

```
# LLM Provider selection (override config.json)
# LLM_PROVIDER=xai
# Available options: xai, anthropic, openai, google
```

Replace the `# Available options:` line with:

```
# Available options: xai, anthropic, openai, google, lmstudio
```

- [ ] **Step 2: Update `CLAUDE.md`**

In [CLAUDE.md](../../../CLAUDE.md), find the Multi-LLM Integration block (line 79-83):

```markdown
- **Multi-LLM Integration**: 
  - X.AI Grok API (vision models: Grok-4, Grok Vision Beta)
  - Anthropic Claude API (PDF support: Claude 4, 3.5/3.7 Sonnet)
  - OpenAI GPT API (vision models: GPT-4o, GPT-4o-mini, o3)
  - Google Vertex AI (vision models: Gemini 2.5 Pro/Flash/Flash-Lite)
```

Append a new bullet at the end of that list:

```markdown
  - LM Studio (local, OpenAI-compatible; vision models supported via rasterized-page upload)
```

So the block becomes:

```markdown
- **Multi-LLM Integration**: 
  - X.AI Grok API (vision models: Grok-4, Grok Vision Beta)
  - Anthropic Claude API (PDF support: Claude 4, 3.5/3.7 Sonnet)
  - OpenAI GPT API (vision models: GPT-4o, GPT-4o-mini, o3)
  - Google Vertex AI (vision models: Gemini 2.5 Pro/Flash/Flash-Lite)
  - LM Studio (local, OpenAI-compatible; vision models supported via rasterized-page upload)
```

- [ ] **Step 3: Update `README.md`**

In [README.md](../../../README.md), find line 12:

```markdown
- **Multi-provider LLM support**: X.AI (Grok), Anthropic (Claude), OpenAI (GPT), Google (Gemini)
```

Replace with:

```markdown
- **Multi-provider LLM support**: X.AI (Grok), Anthropic (Claude), OpenAI (GPT), Google (Gemini), LM Studio (local, OpenAI-compatible)
```

- [ ] **Step 4: Verify docs render sanely**

Run: `cd /Users/efitz/Projects/scan-namer && rg -n "lmstudio|LM Studio|LMSTUDIO_API_KEY" .env.example CLAUDE.md README.md`

Expected: at least one match in each file. No syntax artifacts (e.g., dangling backticks).

- [ ] **Step 5: Commit**

```bash
cd /Users/efitz/Projects/scan-namer
git add .env.example CLAUDE.md README.md
git commit -m "$(cat <<'EOF'
docs(lmstudio): add LM Studio to provider lists and env template

Adds optional LMSTUDIO_API_KEY to .env.example, mentions LM Studio in
the CLAUDE.md Multi-LLM Integration bullet list, and adds it to the
README.md feature line.
EOF
)"
```

---

## Final Verification

- [ ] **Step 1: Confirm full git history is clean**

Run: `cd /Users/efitz/Projects/scan-namer && git log --oneline -5`

Expected: four new commits on top of the previous `HEAD` (in order: refactor extract_usage → feat add LMStudioClient → feat wire factory → docs touch-ups).

- [ ] **Step 2: Final smoke test**

Run: `cd /Users/efitz/Projects/scan-namer && ./scan-namer --provider lmstudio --list-models 2>&1 | rg -i "lmstudio|gemma|qwen"`

Expected: `lmstudio` provider header, `google/gemma-4-31b`, and `qwen/qwen3.6-35b-a3b` appear in the output.

- [ ] **Step 3: (Manual, optional — requires LM Studio running)**

If LM Studio is running locally on port 1234 with one of the configured models loaded, run a real end-to-end test:

```bash
cd /Users/efitz/Projects/scan-namer && ./scan-namer --provider lmstudio --dry-run --verbose 2>&1 | tail -50
```

Look for `LM Studio client initialized: base_url=http://localhost:1234/v1` near the top of the output, and a successful filename suggestion at the end (assuming a generically-named scan exists in the configured Drive folder).
