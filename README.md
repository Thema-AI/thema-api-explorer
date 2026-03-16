# Thema API TUI

Interactive terminal tool for browsing and testing Thema API endpoints.

Fetches the OpenAPI schema dynamically on startup — always shows the latest endpoints.

## Setup

```bash
# clone and install
git clone <repo-url>
cd thema-tui
uv sync

# run
uv run thema-tui

# or with python -m
uv run python -m tui
```

## Usage

| Key      | Action                  |
|----------|-------------------------|
| `e`      | Switch environment      |
| `v`      | Switch service (backend/oracle) |
| `l`      | Login / set credentials |
| `Ctrl+R` | Send request            |
| `q`      | Quit                    |

### Environments

- **local** — `http://localhost:8000`
- **dev** — `https://dev.api.thema.ai`
- **prerelease** — `https://prerelease.api.thema.ai`
- **staging** — `https://staging.api.thema.ai`
- **production** — `https://production.api.thema.ai`

### Workflow

1. Select environment (`e`)
2. Login with your credentials (`l`) — validated against the API and saved to `~/.thema-tui/credentials.json`
3. Browse endpoints in the left tree
4. Click/select an endpoint — the body editor pre-fills with an example
5. For endpoints with path parameters, add `"_path_params": {"id": "your-uuid"}` to the JSON body
6. For query parameters, add `"_query_params": {"key": "value"}` to the JSON body
7. Send with `Ctrl+R` or the Send button
8. View the response in the bottom panel

### Credentials

Credentials are saved per-environment in `~/.thema-tui/credentials.json` (file permissions 600). On startup, saved credentials are auto-validated against the API.
