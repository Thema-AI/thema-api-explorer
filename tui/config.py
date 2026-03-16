"""Credential and environment configuration."""

import json
from pathlib import Path

CONFIG_DIR = Path.home() / ".thema-tui"
CREDENTIALS_FILE = CONFIG_DIR / "credentials.json"

ENVS = ["local", "dev", "prerelease", "staging", "production"]

BACKEND_URLS: dict[str, str] = {
    "local": "http://localhost:8000",
    "dev": "https://dev.api.thema.ai",
    "prerelease": "https://prerelease.api.thema.ai",
    "staging": "https://staging.api.thema.ai",
    "production": "https://production.api.thema.ai",
}

ORACLE_URLS: dict[str, str] = {
    "local": "http://localhost:9000",
    "dev": "https://dev.oracle.thema.ai",
    "prerelease": "https://prerelease.oracle.thema.ai",
    "staging": "https://staging.oracle.thema.ai",
    "production": "https://production.oracle.thema.ai",
}


def _ensure_config_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)


def load_all_credentials() -> dict:
    _ensure_config_dir()
    if CREDENTIALS_FILE.exists():
        return json.loads(CREDENTIALS_FILE.read_text())
    return {}


def save_all_credentials(creds: dict) -> None:
    _ensure_config_dir()
    CREDENTIALS_FILE.write_text(json.dumps(creds, indent=2))
    CREDENTIALS_FILE.chmod(0o600)


def get_env_creds(env: str) -> tuple[str, str] | None:
    creds = load_all_credentials()
    entry = creds.get(env)
    if entry:
        return entry["username"], entry["password"]
    return None


def set_env_creds(env: str, username: str, password: str) -> None:
    creds = load_all_credentials()
    creds[env] = {"username": username, "password": password}
    save_all_credentials(creds)


def remove_env_creds(env: str) -> None:
    creds = load_all_credentials()
    creds.pop(env, None)
    save_all_credentials(creds)
