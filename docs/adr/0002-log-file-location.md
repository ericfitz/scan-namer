# ADR 0002: Log file lives in the XDG state directory and rotates

- Status: Accepted
- Date: 2026-10-07
- Decision maker: Eric Fitzgerald (human decision)

## Context

`logging.file` defaulted to `scan_namer.log` relative to the working
directory, so each run from a different directory left a log there, and the
plain `FileHandler` let the file grow without limit.

## Decision

The log defaults to `$XDG_STATE_HOME/scan-namer/scan_namer.log`, falling back
to `~/.local/state/scan-namer/scan_namer.log` when `XDG_STATE_HOME` is unset,
empty or relative. The directory is created with mode 700. `logging.file` /
`LOG_FILE` still override it; `~` and `$VAR` are expanded, and a relative
value is placed in the default log directory. Logging uses a
`RotatingFileHandler` at 5 MB with 3 backups.

## Consequences

- Existing configs with `"file": "scan_namer.log"` now log to the state
  directory without edits.
- Logs left in old working directories are not migrated.
- Rotation size and count are constants (`LOG_MAX_BYTES`,
  `LOG_BACKUP_COUNT`), not config keys.
