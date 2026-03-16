# Thema API TUI

Interactive terminal tool for browsing and testing Thema API endpoints.

Fetches the OpenAPI schema dynamically on startup — always shows the latest endpoints.

## One-liner (like npx — no clone needed)

```bash
curl -sSL https://raw.githubusercontent.com/Thema-AI/thema-api-explorer/main/run-remote.sh | bash
```

First run installs to `~/.thema-api-explorer/`. Subsequent runs auto-update and start instantly.

Or with `pipx` / `uv`:

```bash
pipx run --spec git+https://github.com/Thema-AI/thema-api-explorer.git thema-api-explorer
uvx --from git+https://github.com/Thema-AI/thema-api-explorer.git thema-api-explorer
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

## Troubleshooting

**`pip install -e .` fails with "setup.py not found"** — upgrade pip first:

```bash
pip install --upgrade pip
pip install -e .
```

## Requirements

- Python 3.11+
