# Thema API TUI

Interactive terminal tool for browsing and testing Thema API endpoints.

Fetches the OpenAPI schema dynamically on startup — always shows the latest endpoints.

## Quick Start

```bash
git clone <repo-url>
cd thema-tui
./run.sh
```

That's it. The script creates a venv, installs deps, and launches the TUI.

## Alternative Setup

```bash
# with pip (any venv)
pip install -e .
thema-tui

# or run directly
python -m tui
```

## Keybindings

| Key      | Action                         |
|----------|--------------------------------|
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

1. Launch — defaults to **dev** environment, schema loads automatically
2. Login (`l`) — enter email/password, validated against the API, saved for next time
3. Browse endpoints in the left tree (grouped by API tag)
4. Select an endpoint — body editor pre-fills with an example from the schema
5. For path parameters, add `"_path_params": {"id": "your-uuid"}` to the JSON body
6. For query parameters, add `"_query_params": {"key": "value"}`
7. Send (`Ctrl+R`) — response appears in the bottom panel with status and timing

## Credentials

Stored per-environment in `~/.thema-tui/credentials.json` (chmod 600). Auto-validated on startup.

## Requirements

- Python 3.11+
