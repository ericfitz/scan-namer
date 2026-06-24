# CLI Overrides & Defaults Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `--provider`/`--model` authoritative overrides with strict validation, fall back to a file for a provider's secret when the env var is unset, and let a configured/`--folder` Google Drive folder skip the selection menu.

**Architecture:** All changes live in `scan_namer.py` plus a one-key addition to `config.json`. Provider/model resolution + hard-fail validation is centralized in `LLMClientFactory.create_client`; secret resolution (env → file) is centralized in `BaseLLMClient` and reused by every client and by Google's project-id lookup; folder resolution is a new `GoogleDriveManager.resolve_folder` wired into `ScanNamer.run`. `ScanNamer.__init__` is reordered to build the LLM client (and run validation) before the eager Google OAuth, so bad flags fail fast.

**Tech Stack:** Python 3.8+, uv (inline script metadata), ruff 0.9.6 for lint. No automated test framework exists in this repo — verification is manual via `./scan-namer` subcommands, consistent with the project's documented testing approach.

## Global Constraints

- Single-file application logic in `scan_namer.py`; config in `config.json`. Follow existing patterns (dot-notation `config.get`, `logging.*`, `sys.exit(1)` on fatal errors).
- Environment variables always win over config/file values (existing invariant).
- Application directory = `os.path.dirname(os.path.abspath(__file__))` (directory containing `scan_namer.py`).
- Lint must pass: `ruff check scan_namer.py` (no new findings).
- No new third-party dependencies.
- The repo has no unit tests; each task ends with a concrete manual verification command + expected output, then a commit.
- Branch off `main` before the first commit (per repo git hygiene); do not push unless asked.

---

## File Structure

- `scan_namer.py` — all code changes (factory resolution, BaseLLMClient secret helpers, client refactors, GoogleDriveManager.resolve_folder, ScanNamer wiring, argparse).
- `config.json` — add `google_drive.folder_name`.
- `.env.example`, `README.md` — document the new `--folder` flag, `folder_name` config key, and API-key file fallback (docs task).

---

## Task 0: Create working branch

**Files:** none (git only)

- [ ] **Step 1: Branch off main**

```bash
git checkout main
git checkout -b feat/cli-overrides-and-defaults
```

- [ ] **Step 2: Confirm clean starting point**

Run: `git status`
Expected: `On branch feat/cli-overrides-and-defaults` and a clean tree.

---

## Task 1: Strict provider/model resolution + fail-fast ordering

Centralize provider/model resolution and convert the model-availability warning into a hard error. Reorder `ScanNamer.__init__` so the LLM client is built (and validated) before the eager Google OAuth.

**Files:**
- Modify: `scan_namer.py` — `LLMClientFactory.create_client` (~1696-1754)
- Modify: `scan_namer.py` — `ScanNamer.__init__` (~1787-1792, the `drive_manager` / `llm_client` creation order)

**Interfaces:**
- Consumes: `config.get("llm.provider")`, `config.get("llm.model")`, `config.get(f"llm.providers.{provider}.default_model")`, `config.get(f"llm.providers.{provider}.available_models")`, `config.get("llm.providers")`.
- Produces: `LLMClientFactory.create_client(config, provider=None, model=None, max_tokens=None) -> BaseLLMClient`. `provider=None`/`model=None` mean "flag not supplied". On any resolution/validation failure it logs an error and calls `sys.exit(1)`.

- [ ] **Step 1: Rewrite the resolution + validation block**

Replace the body of `create_client` from the `if provider is None:` line down to (but not including) the `# Create appropriate client` / `if provider == "xai":` dispatch with:

```python
        # Resolve provider: CLI flag wins, else config default.
        if provider is None:
            provider = config.get("llm.provider", "xai")

        # Validate provider exists before resolving its model.
        providers_config = config.get("llm.providers", {})
        if not isinstance(providers_config, dict) or provider not in providers_config:
            available = list(providers_config) if isinstance(providers_config, dict) else []
            logging.error(f"Unknown provider '{provider}'. Available: {available}")
            sys.exit(1)

        # Resolve model:
        #   --model            -> use it
        #   --provider (no -m) -> that provider's default_model
        #   neither            -> config.llm.model, else provider default_model
        provider_default = config.get(f"llm.providers.{provider}.default_model")
        if model is not None:
            effective_model = model
        elif provider_explicit:
            effective_model = provider_default
        else:
            effective_model = config.get("llm.model") or provider_default
        model = effective_model

        if not model:
            logging.error(
                f"Provider '{provider}' has no default_model configured in config.json"
            )
            sys.exit(1)

        # Validate the resolved model is allowed for this provider (hard fail).
        available_models = config.get(f"llm.providers.{provider}.available_models", [])
        if (
            isinstance(available_models, list)
            and available_models
            and model not in available_models
        ):
            logging.error(
                f"Model '{model}' is not valid for provider '{provider}'. "
                f"Available models for '{provider}': {available_models}"
            )
            sys.exit(1)

        logging.info(f"Using {provider} provider with model: {model}")
```

This block reads a local `provider_explicit` (a boolean) — defined in Step 2. The signature does not change.

- [ ] **Step 2: Capture whether `--provider` was explicitly passed**

The method must distinguish "`--provider` given" from "fell back to config default" before the `if provider is None:` reassignment overwrites that information. Add this as the FIRST line inside `create_client` (before `if provider is None:`):

```python
        provider_explicit = provider is not None
```

It is a plain local, not a new parameter — the signature `def create_client(config, provider=None, model=None, max_tokens=None)` is unchanged.

- [ ] **Step 3: Reorder ScanNamer.__init__ to build the client before Google auth**

In `ScanNamer.__init__`, move the `self.llm_client = LLMClientFactory.create_client(...)` assignment to run BEFORE `self.drive_manager = GoogleDriveManager(self.config)`. Result order:

```python
        # Initialize components.
        # Build the LLM client first so invalid --provider/--model fail fast,
        # before the eager Google Drive OAuth round-trip.
        self.llm_client = LLMClientFactory.create_client(
            self.config, provider=provider, model=model, max_tokens=max_tokens
        )
        self.pdf_processor = PDFProcessor(self.config)
        self.drive_manager = GoogleDriveManager(self.config)
```

Keep the existing `--no-ocr` capability-validation block (uses `self.llm_client`) where it is, after these assignments.

- [ ] **Step 4: Lint**

Run: `ruff check scan_namer.py`
Expected: no new findings (exit 0).

- [ ] **Step 5: Verify provider-only uses provider default (no model required)**

Run: `./scan-namer --provider anthropic --list-models`

`--list-models` exits before client creation, so it does not exercise resolution. Instead verify resolution via Python using the factory directly:

Run:
```bash
uv run scan_namer.py --provider anthropic --model gpt-5.5 --dry-run 2>&1 | rg "is not valid for provider"
```
Expected: a line like `Model 'gpt-5.5' is not valid for provider 'anthropic'. Available models for 'anthropic': [...]` and the process exits non-zero BEFORE any Google OAuth prompt.

- [ ] **Step 6: Verify model-only mismatch against default provider errors**

Run:
```bash
uv run scan_namer.py --model claude-sonnet-4-6 --dry-run 2>&1 | rg "is not valid for provider 'openai'"
```
Expected: error naming provider `openai` (config default) and exit before Google OAuth.

- [ ] **Step 7: Verify provider-only resolves to provider default model**

Run:
```bash
uv run scan_namer.py --provider anthropic --dry-run 2>&1 | rg "Using anthropic provider with model:"
```
Expected: `Using anthropic provider with model: claude-sonnet-4-6` (anthropic's `default_model`), then it proceeds toward Google auth (which may then prompt/fail — that is fine; the resolution log is what we verify).

- [ ] **Step 8: Commit**

```bash
git add scan_namer.py
git commit -m "feat(scan_namer): strict provider/model resolution with fail-fast validation"
```

---

## Task 2: API-key (and project-id) file fallback

Add shared secret resolution to `BaseLLMClient` (env → file in app dir), use it from a shared `_get_api_key`, remove the three duplicated overrides, and route LM Studio + Google through it.

**Files:**
- Modify: `scan_namer.py` — `BaseLLMClient` (add helpers + shared `_get_api_key`, ~595-648 region)
- Modify: `scan_namer.py` — remove `XAIClient._get_api_key` (~729-740), `AnthropicClient._get_api_key` (~1061-1067), `OpenAIClient._get_api_key` (~1231-1237)
- Modify: `scan_namer.py` — `LMStudioClient._get_api_key` (~1464-1478)
- Modify: `scan_namer.py` — `GoogleClient._get_project_id` (~1526-1534)

**Interfaces:**
- Produces on `BaseLLMClient`:
  - `_resolve_secret(self, env_var_name: str) -> Optional[str]` — returns env value if set/non-empty, else parsed value from a file named exactly `env_var_name` in the app dir, else `None`.
  - `_parse_secret_file(self, path: str, env_var_name: str) -> Optional[str]` — parses `export VAR=...` / `VAR="..."` / raw-key file content.
  - `_get_api_key(self) -> str` — resolves `llm.providers.{provider}.api_key_env`; `sys.exit(1)` with a message naming both env var and file if unresolved.
- Consumes: existing `self.config`, `self.provider`; module-level `APP_DIR`.

- [ ] **Step 1: Add the module-level app-dir constant**

Near the top of `scan_namer.py`, after the imports / `prefer_ipv4` definition (before `class ConfigManager`), add:

```python
APP_DIR = os.path.dirname(os.path.abspath(__file__))
```

- [ ] **Step 2: Add the `re` import**

Confirm `import re` exists at the top of the file; if not, add it in the stdlib import group (alphabetically near `import os`). It is needed by `_parse_secret_file`.

- [ ] **Step 3: Add secret helpers + shared `_get_api_key` to BaseLLMClient**

Insert these methods into `BaseLLMClient` (e.g. directly after `_encode_pdf_to_base64`):

```python
    def _parse_secret_file(self, path: str, env_var_name: str) -> Optional[str]:
        """Read a secret from a file.

        Accepts either a raw secret (the file's first non-empty line) or a
        shell-style assignment line such as:
            export ANTHROPIC_API_KEY=foo
            ANTHROPIC_API_KEY="foo"
        Surrounding single/double quotes on an assignment value are stripped.
        """
        try:
            with open(path, "r") as f:
                lines = f.readlines()
        except OSError as e:
            logging.warning(f"Could not read secret file {path}: {e}")
            return None

        assign = re.compile(
            rf"^\s*(?:export\s+)?{re.escape(env_var_name)}\s*=\s*(.+?)\s*$"
        )
        for line in lines:
            m = assign.match(line)
            if m:
                value = m.group(1)
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                return value or None

        for line in lines:
            stripped = line.strip()
            if stripped:
                return stripped
        return None

    def _resolve_secret(self, env_var_name: str) -> Optional[str]:
        """Resolve a secret from the environment, else an app-dir file.

        The environment always wins. The file must be named exactly
        ``env_var_name`` (no extension) and live in the application directory.
        """
        value = os.getenv(env_var_name)
        if value:
            return value
        path = os.path.join(APP_DIR, env_var_name)
        if os.path.isfile(path):
            return self._parse_secret_file(path, env_var_name)
        return None

    def _get_api_key(self) -> str:
        """Resolve this provider's API key from env or app-dir file."""
        api_key_env = self.config.get(f"llm.providers.{self.provider}.api_key_env")
        if not isinstance(api_key_env, str):
            logging.error(
                f"Invalid API key environment variable name for {self.provider}"
            )
            sys.exit(1)
        api_key = self._resolve_secret(api_key_env)
        if not api_key:
            logging.error(
                f"API key not found. Set environment variable {api_key_env} or "
                f"place it in a file named {api_key_env} in {APP_DIR}."
            )
            sys.exit(1)
        return api_key
```

- [ ] **Step 4: Remove the three duplicated overrides**

Delete the entire `_get_api_key` method from each of:
- `XAIClient` (~729-740)
- `AnthropicClient` (~1061-1067)
- `OpenAIClient` (~1231-1237)

Leave each client's `self.api_key = self._get_api_key()` call in its `__init__` intact — it now resolves to the inherited base method.

- [ ] **Step 5: Route LMStudioClient through the resolver**

Replace `LMStudioClient._get_api_key` body with:

```python
    def _get_api_key(self) -> str:
        """Return the configured API key, or a placeholder if unset.

        LM Studio does not authenticate by default. Resolve from env or an
        app-dir file named after ``api_key_env``; if neither is present, return
        a non-empty placeholder so the openai SDK does not refuse to construct.
        """
        api_key_env = self.config.get(f"llm.providers.{self.provider}.api_key_env")
        if isinstance(api_key_env, str):
            api_key = self._resolve_secret(api_key_env)
            if api_key:
                return api_key
        return "lm-studio"
```

- [ ] **Step 6: Route GoogleClient project-id through the resolver**

Replace `GoogleClient._get_project_id` body with:

```python
    def _get_project_id(self) -> str:
        project_env = self.config.get(f"llm.providers.{self.provider}.project_id_env")
        if not isinstance(project_env, str):
            logging.error(f"Invalid project ID environment variable name for {self.provider}")
            sys.exit(1)
        project_id = self._resolve_secret(project_env)
        if not project_id:
            logging.error(
                f"Project ID not found. Set environment variable {project_env} or "
                f"place it in a file named {project_env} in {APP_DIR}."
            )
            sys.exit(1)
        return project_id
```

- [ ] **Step 7: Lint**

Run: `ruff check scan_namer.py`
Expected: no new findings.

- [ ] **Step 8: Verify file fallback (assignment form) resolves a key**

```bash
printf 'export ANTHROPIC_API_KEY="sk-test-123"\n' > ANTHROPIC_API_KEY
env -u ANTHROPIC_API_KEY uv run scan_namer.py --provider anthropic --dry-run 2>&1 | rg -v "sk-test-123" | rg "API key not found" ; echo "exit_match=$?"
rm -f ANTHROPIC_API_KEY
```
Expected: NO `API key not found` line (so `rg` prints nothing and `exit_match=1`). The run proceeds past key resolution toward Google auth. (The key value itself is never logged.)

- [ ] **Step 9: Verify raw-key file form resolves a key**

```bash
printf 'sk-raw-test\n' > ANTHROPIC_API_KEY
env -u ANTHROPIC_API_KEY uv run scan_namer.py --provider anthropic --dry-run 2>&1 | rg "API key not found"; echo "found=$?"
rm -f ANTHROPIC_API_KEY
```
Expected: no `API key not found` line (`found=1`).

- [ ] **Step 10: Verify missing env + missing file errors with the new message**

```bash
env -u ANTHROPIC_API_KEY uv run scan_namer.py --provider anthropic --dry-run 2>&1 | rg "place it in a file named ANTHROPIC_API_KEY"
```
Expected: the new error line appears and the process exits before Google auth.

- [ ] **Step 11: Commit**

```bash
git add scan_namer.py
git commit -m "feat(scan_namer): resolve provider secrets from env or app-dir file"
```

---

## Task 3: Default Google Drive folder

Add the config key, the `--folder` flag, `GoogleDriveManager.resolve_folder`, and wire it into `ScanNamer.run`.

**Files:**
- Modify: `config.json` — add `google_drive.folder_name`
- Modify: `scan_namer.py` — `GoogleDriveManager` (add `resolve_folder`, after `select_folder` ~315)
- Modify: `scan_namer.py` — `ScanNamer.__init__` (add `folder_name` param) and `ScanNamer.run` (~2122 folder selection)
- Modify: `scan_namer.py` — `main()` argparse + `ScanNamer(...)` call (~2238, ~2313)

**Interfaces:**
- Consumes: `config.get("google_drive.folder_name")`, `GoogleDriveManager.list_folders()` (root scope), `GoogleDriveManager.select_folder()`.
- Produces: `GoogleDriveManager.resolve_folder(self, name: str) -> Optional[str]` — returns a folder id on a unique case-insensitive root match, else `None` (after logging a warning). `ScanNamer.__init__(..., folder_name: Optional[str] = None)`.

- [ ] **Step 1: Add the config key**

In `config.json`, add `"folder_name": ""` to the `google_drive` object:

```json
  "google_drive": {
    "credentials_file": "credentials.json",
    "token_file": "token.json",
    "folder_name": "",
    "scopes": [
      "https://www.googleapis.com/auth/drive"
    ]
  },
```

- [ ] **Step 2: Verify config still parses**

Run: `uv run scan_namer.py --list-providers`
Expected: prints the provider list (proves `config.json` is valid JSON and loads).

- [ ] **Step 3: Add `resolve_folder` to GoogleDriveManager**

Insert after `select_folder` (after line ~315):

```python
    def resolve_folder(self, name: str) -> Optional[str]:
        """Resolve a root folder by name (case-insensitive).

        Returns the folder id on a single unambiguous match. On no match or
        multiple matches, logs a warning and returns None so the caller can
        fall back to the interactive selection menu.
        """
        folders = self.list_folders()
        matches = [f for f in folders if f.get("name", "").lower() == name.lower()]
        if len(matches) == 1:
            selected = matches[0]
            logging.info(
                f"Using configured folder: {selected['name']} (ID: {selected['id']})"
            )
            return selected["id"]
        if not matches:
            logging.warning(
                f"Folder '{name}' not found in Google Drive root; showing selection menu"
            )
        else:
            logging.warning(
                f"Multiple folders named '{name}' found; showing selection menu"
            )
        return None
```

- [ ] **Step 4: Add `folder_name` to ScanNamer.__init__**

Add the parameter to the signature (after `download_dir`):

```python
        download_dir: Optional[str] = None,
        folder_name: Optional[str] = None,
```

And store it (near where `self.no_ocr` etc. are set):

```python
        self.folder_name = folder_name
```

- [ ] **Step 5: Wire folder resolution into ScanNamer.run**

Replace the existing folder-selection block in `run` (currently):

```python
            # Select folder
            folder_id = self.drive_manager.select_folder()
            if not folder_id:
                logging.error("No folder selected")
                return
```

with:

```python
            # Resolve folder: CLI --folder > config google_drive.folder_name.
            # A unique name match skips the menu; otherwise fall back to it.
            effective_folder_name = self.folder_name or self.config.get(
                "google_drive.folder_name"
            )
            folder_id = None
            if effective_folder_name:
                folder_id = self.drive_manager.resolve_folder(effective_folder_name)
            if not folder_id:
                folder_id = self.drive_manager.select_folder()
            if not folder_id:
                logging.error("No folder selected")
                return
```

- [ ] **Step 6: Add the `--folder` argument**

In `main()`'s argparse block (alongside the other `add_argument` calls), add:

```python
    parser.add_argument(
        "--folder",
        help="Google Drive folder name to use (overrides config google_drive.folder_name); skips the menu when uniquely matched",
        metavar="NAME",
    )
```

- [ ] **Step 7: Pass `--folder` into ScanNamer**

In the `app = ScanNamer(...)` construction in `main()`, add:

```python
            folder_name=args.folder,
```

- [ ] **Step 8: Lint**

Run: `ruff check scan_namer.py`
Expected: no new findings.

- [ ] **Step 9: Verify the flag is wired and help renders**

Run: `uv run scan_namer.py --help`
Expected: help text includes `--folder NAME`.

- [ ] **Step 10: Verify folder resolution end-to-end (requires Google auth)**

With valid Google credentials and a unique root folder named e.g. `Scans`:

Run: `./scan-namer --folder Scans --dry-run --verbose 2>&1 | rg "Using configured folder|not found|Multiple folders"`
Expected: `Using configured folder: Scans (ID: ...)` and NO interactive menu. Then run with a bogus name:
Run: `./scan-namer --folder NoSuchFolder123 --dry-run 2>&1 | rg "not found in Google Drive root"`
Expected: the warning prints, followed by the normal selection menu.

(If Google credentials are unavailable in the working environment, note this step as deferred to manual user testing — the code path is exercised by Steps 8-9 for wiring/lint.)

- [ ] **Step 11: Commit**

```bash
git add scan_namer.py config.json
git commit -m "feat(scan_namer): default Google Drive folder via config and --folder"
```

---

## Task 4: Documentation

Document the new flag, config key, and secret-file fallback so the docs listed in CLAUDE.md stay accurate.

**Files:**
- Modify: `.env.example` (note the file-fallback option)
- Modify: `README.md` (new `--folder` flag, `folder_name` config key, secret-file fallback)

**Interfaces:** none (docs only).

- [ ] **Step 1: Document the secret-file fallback in `.env.example`**

After the `API CREDENTIALS` header comment block, add a note:

```
# If an API key is not set in the environment, scan-namer will also look for a
# file named exactly like the env var (e.g. ANTHROPIC_API_KEY) in the application
# directory. The file may contain the raw key, or a line like:
#   export ANTHROPIC_API_KEY="sk-..."
# The same fallback applies to GOOGLE_PROJECT_ID.
```

- [ ] **Step 2: Document `--folder` and `folder_name` + secret fallback in `README.md`**

Add a short subsection (under the existing usage/configuration docs) describing:
- `--folder NAME` overrides `google_drive.folder_name`; a unique root-folder name match skips the menu, otherwise the menu is shown.
- `google_drive.folder_name` config key (default empty = always show menu).
- The env-or-file secret resolution for provider API keys and `GOOGLE_PROJECT_ID`.

Match the surrounding README formatting (headers/code fences already used in that file).

- [ ] **Step 3: Verify docs render / no broken references**

Run: `rg -n "folder_name|--folder|file named" README.md .env.example`
Expected: the new lines appear in both files.

- [ ] **Step 4: Commit**

```bash
git add README.md .env.example
git commit -m "docs(scan_namer): document --folder, folder_name, and secret-file fallback"
```

---

## Self-Review Notes

- **Spec coverage:**
  - §1 provider/model resolution + 3 error cases + per-provider default_model → Task 1.
  - §2 env-then-file secret fallback, app dir, parse rules, centralization, LMStudio placeholder, Google parity → Task 2.
  - §3 config key, `--folder`, root-only resolution with 1/0/>1 handling, run wiring → Task 3.
  - Docs (files named in CLAUDE.md) → Task 4.
- **Fail-fast reorder** (client before Drive auth) is an addition beyond the spec text but is implied by the spec's "informative error message" UX and makes the Task 1 verification possible without OAuth; called out explicitly in Task 1 Step 3.
- **Type consistency:** `resolve_folder` returns `Optional[str]` (folder id) consistent with `select_folder`. `_resolve_secret`/`_parse_secret_file` return `Optional[str]`; `_get_api_key` returns `str` (exits on None). `provider_explicit` is a local boolean in `create_client`.
- **No placeholders:** every code step shows the actual code; verification steps give exact commands and expected output.
