# ADR 0001: Config file lives in the XDG config directory

- Status: Accepted
- Date: 2026-10-07
- Decision maker: Eric Fitzgerald (human decision)

## Context

`config.json` was read from the current working directory, so scan-namer
only worked when run from the repo root, and the instance-specific config
sat in the repo tree (git-ignored).

## Decision

The default config path for `scan-namer` and `update-models` is
`$XDG_CONFIG_HOME/scan-namer/config.json`, falling back to
`~/.config/scan-namer/config.json` when `XDG_CONFIG_HOME` is unset, empty
or relative (per the XDG Base Directory spec). `--config FILE` still selects another
file; `~` and `$VAR`/`${VAR}` are expanded. `config.json.example` stays in
the repo as the template. `prompts.json` is read from the script's
directory, and the `scan-namer` wrapper resolves its own location, so both
tools run from any directory.

## Consequences

- New setups copy `config.json.example` into that directory.
- Relative paths inside the config (e.g. `logging.file: scan_namer.log`)
  still resolve against the working directory.
- `XDG_CONFIG_HOME` support was added at Eric's request (human decision,
  2026-10-07). It is not set in the shell profile; the fallback applies.
