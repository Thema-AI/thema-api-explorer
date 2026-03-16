# Thema API TUI

Interactive terminal tool for browsing and testing Thema API endpoints.

Fetches the OpenAPI schema dynamically on startup — always shows the latest endpoints.

## One-liner (like npx — no clone needed)

Just paste and run (needs `python3` + GitHub SSH access):

```bash
bash <(gh api repos/Thema-AI/thema-api-explorer/contents/run-remote.sh -q '.content' | base64 -d)
```

Or copy-paste this self-contained version:

```bash
D=~/.thema-api-explorer; [ -d "$D/.git" ] && git -C "$D" pull -q || git clone -q git@github.com:Thema-AI/thema-api-explorer.git "$D"; [ -d "$D/.venv" ] || python3 -m venv "$D/.venv"; source "$D/.venv/bin/activate"; pip install -q -e "$D"; thema-api-explorer
```

First run clones + installs to `~/.thema-api-explorer/`. Subsequent runs pull latest and start instantly.

With `pipx` / `uv`:

```bash
pipx run --spec git+ssh://git@github.com/Thema-AI/thema-api-explorer.git thema-api-explorer
uvx --from git+ssh://git@github.com/Thema-AI/thema-api-explorer.git thema-api-explorer
```

## Quick Start (from clone)

```bash
git clone git@github.com:Thema-AI/thema-api-explorer.git
cd thema-api-explorer
./run.sh
```

The script creates a venv, installs deps, and launches the TUI.

## First Run

On first launch a setup wizard lets you pick your environment (defaults to **dev**) and service (defaults to **backend**). Your choice is remembered for next time.

Login later with `l` — credentials are validated against the API and saved per-environment.

## Keybindings

| Key      | Action                         |
|----------|--------------------------------|
| `/`      | Search endpoints               |
| `e`      | Switch environment             |
| `v`      | Switch service (backend/oracle)|
| `l`      | Login / set credentials        |
| `Ctrl+R` | Send request                   |
| `q`      | Quit                           |

## Environments

| Name         | Backend URL                          |
|--------------|--------------------------------------|
| local        | `http://localhost:8000`              |
| dev          | `https://dev.api.thema.ai`          |
| prerelease   | `https://prerelease.api.thema.ai`   |
| staging      | `https://staging.api.thema.ai`      |
| production   | `https://production.api.thema.ai`   |

## Workflow

1. Launch — setup wizard on first run, then schema loads automatically
2. Search endpoints with `/` — matches path, method, summary, tags
3. Select an endpoint — parameter inputs and body editor pre-fill from the schema
4. Fill in path/query parameters in the input fields
5. Edit the JSON body if needed
6. Send (`Ctrl+R`) — response with status, timing, and formatted JSON
7. Login (`l`) when you need authenticated endpoints

## Credentials & State

- Credentials: `~/.thema-tui/credentials.json` (chmod 600)
- Session state (env, service): `~/.thema-tui/state.json`

Both are auto-restored on next launch.

## Requirements

- Python 3.11+
