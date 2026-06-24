# Design: Provider/Model Overrides, API-Key File Fallback, and Default Drive Folder

Date: 2026-06-24
Status: Approved

## Overview

Three related changes to `scan_namer.py` (and `config.json`):

1. Make `--provider`/`--model` CLI flags authoritative overrides of `config.json`,
   with strict validation that hard-exits on an invalid provider/model combination.
2. When a provider's API key is absent from the environment, fall back to reading
   it from a file (named exactly like the env var) in the application directory.
3. Add a default Google Drive folder (config value + `--folder` CLI override) so the
   selection menu can be skipped when the folder is unambiguously found.

No automated tests exist in this project; validation is manual via `--dry-run`,
`--list-models`, and `--list-providers`.

## 1. Provider & Model Resolution

### Current behavior
In `LLMClientFactory.create_client`:
- `provider` defaults to `config.llm.provider`.
- `model` defaults to `config.llm.model` regardless of provider, then to the
  provider's `default_model` only if `config.llm.model` is empty.
- A model not in the provider's `available_models` produces a **warning** and
  proceeds anyway.

### New behavior
Resolution order:

```
effective_provider = (--provider)  or  config.llm.provider

effective_model =
    (--model)                                      if --model was given
    else providers[effective_provider].default_model   if --provider was given (and no --model)
    else config.llm.model                          (fall back to provider default_model if absent/empty)
```

Rationale for the middle branch: when the user explicitly names a provider but no
model, do not force them to specify a model — use that provider's `default_model`.
The global `config.llm.model` is tied to the default provider and must not leak
into a different, explicitly-chosen provider.

### Validation (hard exit, replacing the current warning)
After resolution, validate and exit with `sys.exit(1)` and an informative message:

- Unknown provider:
  `Unknown provider 'X'. Available: [<provider list>]`
- Missing `default_model` for the chosen provider (config integrity guard):
  `Provider 'X' has no default_model configured in config.json`
- Model not valid for provider:
  `Model 'Y' is not valid for provider 'X'. Available models for 'X': [<model list>]`

This produces exactly the three required error cases:
- `--model Y` alone where Y is not in the default provider's `available_models` → error.
- `--provider X --model Y` where Y is not in X's `available_models` → error.
- `--provider X` alone → uses X's `default_model` (always valid by construction;
  never forces the user to pass `--model`).

### Touch points
- `LLMClientFactory.create_client` (around line 1700): rework the
  provider/model defaulting block and convert the model-availability warning into
  a hard error. The factory must know whether `--provider`/`--model` were
  explicitly passed; since `ScanNamer.__init__` already receives `provider`/`model`
  as `Optional[str]` (None when absent), the existing `None` sentinels are
  sufficient to distinguish "explicitly given" from "not given".

## 2. API-Key File Fallback

### Current behavior
Four near-identical `_get_api_key` methods (XAIClient ~729, AnthropicClient ~1061,
OpenAIClient ~1231, LMStudioClient ~1464) each read `os.getenv(api_key_env)` and
error if unset. `GoogleClient._get_project_id` (~1526) reads `project_id_env` from
the environment only. LMStudioClient additionally falls back to a `"lm-studio"`
placeholder.

### New behavior
Add a single shared helper on `BaseLLMClient`:

```
def _resolve_secret(self, env_var_name: str) -> Optional[str]:
    # 1. Environment always wins.
    value = os.getenv(env_var_name)
    if value:
        return value
    # 2. Fall back to a file named exactly env_var_name in the application directory.
    #    Application directory = directory containing scan_namer.py.
    path = os.path.join(<app_dir>, env_var_name)
    if os.path.isfile(path):
        return _parse_secret_file(path, env_var_name)
    return None
```

Application directory is computed once as
`os.path.dirname(os.path.abspath(__file__))`.

File parsing (`_parse_secret_file`):
1. Read the file's lines.
2. For each line, try to match `^\s*(export\s+)?<ENV_VAR>\s*=\s*(.+?)\s*$`.
   If matched, take the captured value and strip a single pair of surrounding
   single or double quotes. Return it.
3. If no assignment line matches, return the first non-empty line, trimmed
   (the "raw key in a file" case).
4. If the file is empty/whitespace-only, return `None`.

Refactor the four provider clients to use `_resolve_secret(api_key_env)`:
- XAI / Anthropic / OpenAI: remove their `_get_api_key` overrides; `BaseLLMClient`
  provides `_get_api_key` that resolves the secret and errors if `None`. The error
  message is updated to name both the env var and the expected file, e.g.:
  `API key not found. Set environment variable ANTHROPIC_API_KEY or place it in a
  file named ANTHROPIC_API_KEY in <app_dir>.`
- LMStudioClient: keep its override but route through `_resolve_secret`, returning
  the `"lm-studio"` placeholder when the resolver yields `None`.
- GoogleClient: route `_get_project_id` through `_resolve_secret(project_id_env)`
  for parity, so Google users get the same file fallback. Its error message is
  updated to mention the file fallback as well.

The `api_key_env` value may be missing/invalid in config; preserve the existing
guard (XAIClient currently checks `isinstance(api_key_env, str)`) by validating in
the shared `_get_api_key` before resolving.

## 3. Default Google Drive Folder

### Config
Add to `config.json` under `google_drive`:

```
"folder_name": ""
```

Empty string (or absent) means "no default — always show the menu", preserving
current behavior.

### CLI
Add `--folder NAME` argument (overrides `config.google_drive.folder_name`).
Plumb it through `ScanNamer.__init__` as `folder_name: Optional[str] = None`.

### Resolution (`GoogleDriveManager.resolve_folder`)
New method `resolve_folder(self, name: str) -> Optional[str]`:
- List **root** folders (reuse existing `list_folders()`, root scope — same scope
  as the current menu).
- Match by name, case-insensitive.
  - Exactly 1 match → log the chosen folder and return its id.
  - 0 matches → `logging.warning("Folder 'NAME' not found in Google Drive root; showing selection menu")`, return `None`.
  - >1 matches → `logging.warning("Multiple folders named 'NAME' found; showing selection menu")`, return `None`.

### Wiring (`ScanNamer.run`)
Compute `effective_folder_name = self.folder_name or config.google_drive.folder_name`.
- If `effective_folder_name` is non-empty: call `resolve_folder`. If it returns an
  id, use it; if it returns `None`, fall through to the existing
  `select_folder()` menu.
- If empty: existing `select_folder()` menu, unchanged.

## Scope / Non-Goals

- No new environment-variable override for provider/model beyond the existing
  `LLM_PROVIDER` / `LLM_MODEL` (which feed `config.llm.*`; CLI flags override the
  resolved config values).
- No env-var override for `--folder` (not requested).
- No automated test framework added; manual validation only.
- `--folder` matches by name (not folder id); the custom-path entry in the existing
  menu still accepts an id/path.

## Files Touched

- `config.json`: add `google_drive.folder_name`.
- `scan_namer.py`:
  - `LLMClientFactory.create_client`: new resolution + hard-error validation.
  - `BaseLLMClient`: add `_resolve_secret`, `_parse_secret_file`, shared
    `_get_api_key`; app-dir constant.
  - Remove `_get_api_key` overrides in XAIClient/AnthropicClient/OpenAIClient.
  - LMStudioClient `_get_api_key`: route through `_resolve_secret`.
  - GoogleClient `_get_project_id`: route through `_resolve_secret`.
  - `GoogleDriveManager`: add `resolve_folder`.
  - `ScanNamer.__init__` / `run`: add `folder_name`, wire folder resolution.
  - `main()` / argparse: add `--folder`; pass through.

## Manual Validation Plan

- `./scan-namer --list-models` / `--list-providers` still work.
- `./scan-namer --provider anthropic --dry-run` → uses `claude-sonnet-4-6`
  (anthropic default), no model required.
- `./scan-namer --provider anthropic --model gpt-5.5 --dry-run` → hard error
  (model invalid for provider).
- `./scan-namer --model claude-sonnet-4-6 --dry-run` (default provider openai) →
  hard error (model invalid for default provider).
- Unset `ANTHROPIC_API_KEY`, create file `ANTHROPIC_API_KEY` containing
  `export ANTHROPIC_API_KEY="test"` → key resolves to `test`. Repeat with a raw
  one-line file.
- Set `google_drive.folder_name` to an existing unique root folder → menu skipped.
  Set to a non-existent name → warning + menu. Set to a duplicated name → warning +
  menu. `--folder` overrides config in each case.
