"""Thema API TUI - Interactive terminal tool for browsing and testing API endpoints."""

from __future__ import annotations

import json
import re

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
    RichLog,
    Static,
    TextArea,
    Tree,
)
from textual.widgets.option_list import Option

from tui.client import APIClient, APIResponse
from tui.config import (
    BACKEND_URLS,
    ENVS,
    ORACLE_URLS,
    get_env_creds,
    set_env_creds,
)
from tui.schema import APISchema, Endpoint, fetch_schema, generate_example

# ---------------------------------------------------------------------------
# Login modal
# ---------------------------------------------------------------------------


class LoginScreen(ModalScreen[tuple[str, str] | None]):
    """Modal screen for entering credentials."""

    CSS = """
    LoginScreen {
        align: center middle;
    }
    #login-box {
        width: 60;
        height: auto;
        max-height: 20;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    #login-box Label {
        margin-bottom: 1;
    }
    #login-box Input {
        margin-bottom: 1;
    }
    #login-buttons {
        height: auto;
        margin-top: 1;
        align-horizontal: right;
    }
    #login-buttons Button {
        margin-left: 1;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="login-box"):
            yield Label("Login to environment", id="login-title")
            yield Label("Username (email):")
            yield Input(placeholder="user@example.com", id="login-username")
            yield Label("Password:")
            yield Input(placeholder="password", password=True, id="login-password")
            with Horizontal(id="login-buttons"):
                yield Button("Cancel", variant="default", id="login-cancel")
                yield Button("Login", variant="primary", id="login-submit")

    def on_mount(self) -> None:
        self.query_one("#login-username", Input).focus()

    @on(Button.Pressed, "#login-cancel")
    def cancel(self) -> None:
        self.dismiss(None)

    @on(Button.Pressed, "#login-submit")
    def submit(self) -> None:
        username = self.query_one("#login-username", Input).value.strip()
        password = self.query_one("#login-password", Input).value
        if username and password:
            self.dismiss((username, password))

    @on(Input.Submitted)
    def on_input_submitted(self) -> None:
        self.submit()


# ---------------------------------------------------------------------------
# Environment selector modal
# ---------------------------------------------------------------------------


class EnvScreen(ModalScreen[str | None]):
    CSS = """
    EnvScreen {
        align: center middle;
    }
    #env-box {
        width: 40;
        height: auto;
        max-height: 22;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="env-box"):
            yield Label("Select Environment")
            yield OptionList(
                *[Option(env, id=env) for env in ENVS],
                id="env-list",
            )

    def on_mount(self) -> None:
        self.query_one("#env-list", OptionList).focus()

    @on(OptionList.OptionSelected, "#env-list")
    def on_select(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(ENVS[event.option_index])


# ---------------------------------------------------------------------------
# Service selector modal
# ---------------------------------------------------------------------------


class ServiceScreen(ModalScreen[str | None]):
    CSS = """
    ServiceScreen {
        align: center middle;
    }
    #svc-box {
        width: 40;
        height: auto;
        border: thick $accent;
        background: $surface;
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="svc-box"):
            yield Label("Select Service")
            yield OptionList(
                Option("backend", id="backend"),
                Option("oracle", id="oracle"),
                id="svc-list",
            )

    def on_mount(self) -> None:
        self.query_one("#svc-list", OptionList).focus()

    @on(OptionList.OptionSelected, "#svc-list")
    def on_select(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(["backend", "oracle"][event.option_index])


# ---------------------------------------------------------------------------
# Main Application
# ---------------------------------------------------------------------------

METHOD_COLORS = {
    "GET": "green",
    "POST": "cyan",
    "PUT": "yellow",
    "PATCH": "yellow",
    "DELETE": "red",
}


class ThemaApp(App):
    CSS = """
    #main-area {
        height: 1fr;
    }
    #sidebar {
        width: 44;
        min-width: 30;
        border-right: solid $accent;
    }
    #sidebar-header {
        height: auto;
        padding: 0 1;
        background: $boost;
    }
    #endpoint-tree {
        height: 1fr;
    }
    #detail-area {
        width: 1fr;
    }
    #endpoint-info {
        height: auto;
        max-height: 8;
        padding: 0 1;
        border-bottom: solid $accent;
    }
    #params-area {
        height: auto;
        max-height: 16;
        padding: 0 1;
        border-bottom: solid $accent;
    }
    .param-row {
        height: auto;
        layout: horizontal;
    }
    .param-label {
        width: 20;
        height: 3;
        content-align-vertical: middle;
    }
    .param-input {
        width: 1fr;
        height: 3;
    }
    #body-area {
        height: 1fr;
        min-height: 8;
    }
    #body-editor {
        height: 1fr;
    }
    #action-bar {
        height: auto;
        padding: 0 1;
        align-horizontal: left;
        border-bottom: solid $accent;
    }
    #action-bar Button {
        margin-right: 1;
    }
    #response-area {
        height: 1fr;
        min-height: 10;
    }
    #response-header {
        height: auto;
        padding: 0 1;
        background: $boost;
    }
    #response-log {
        height: 1fr;
    }
    #status-bar {
        height: auto;
        padding: 0 1;
        background: $boost;
        dock: bottom;
    }
    """

    TITLE = "Thema API TUI"
    BINDINGS = [
        Binding("e", "switch_env", "Environment"),
        Binding("v", "switch_service", "Service"),
        Binding("l", "login", "Login"),
        Binding("ctrl+r", "send_request", "Send"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_env: str = "dev"
        self.current_service: str = "backend"
        self.api_client = APIClient(base_url=BACKEND_URLS["dev"])
        self.schema: APISchema | None = None
        self.selected_endpoint: Endpoint | None = None
        self._raw_openapi: dict = {}

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            with Vertical(id="sidebar"):
                yield Static(self._sidebar_header_text(), id="sidebar-header")
                yield Tree("Endpoints", id="endpoint-tree")
            with Vertical(id="detail-area"):
                yield Static("Select an endpoint from the tree.", id="endpoint-info")
                with VerticalScroll(id="params-area"):
                    yield Static("", id="params-container")
                with Vertical(id="body-area"):
                    yield TextArea("", language="json", id="body-editor", theme="monokai")
                with Horizontal(id="action-bar"):
                    yield Button("Send (Ctrl+R)", variant="primary", id="btn-send")
                    yield Button("Reset Body", variant="default", id="btn-reset")
                yield Static("", id="response-header")
                yield RichLog(highlight=True, markup=True, wrap=True, id="response-log")
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = f"{self.current_env} | {self.current_service}"
        self._auto_login_and_load()

    @work(exclusive=True, group="init")
    async def _auto_login_and_load(self) -> None:
        """Try saved creds, then load schema."""
        creds = get_env_creds(self.current_env)
        if creds:
            username, password = creds
            self._log(f"Authenticating as {username}...")
            resp = await self.api_client.authenticate(username, password)
            if resp.ok:
                self._log(f"Authenticated ({resp.elapsed_ms:.0f}ms)")
            else:
                self._log(f"[red]Auth failed:[/] {resp.status_code} {resp.body[:200]}")

        # Fetch schema (inline, not via another @work)
        base_url = self._current_base_url()
        self._log(f"Fetching schema from {base_url}/v1/openapi.json ...")
        try:
            self.schema = await fetch_schema(base_url)
            self._log(
                f"Loaded {len(self.schema.endpoints)} endpoints "
                f"({self.schema.title} v{self.schema.version})"
            )
            self._populate_tree()
        except Exception as exc:
            self._log(f"[red]Failed to load schema:[/] {exc}")

    def _populate_tree(self) -> None:
        tree = self.query_one("#endpoint-tree", Tree)
        tree.clear()
        tree.root.expand()
        if not self.schema:
            return
        for tag, endpoints in sorted(self.schema.by_tag().items()):
            branch = tree.root.add(tag, expand=False)
            for ep in endpoints:
                color = METHOD_COLORS.get(ep.method, "white")
                label = f"[{color}]{ep.method:6s}[/] {ep.path}"
                branch.add_leaf(label, data=ep)

    @on(Tree.NodeSelected, "#endpoint-tree")
    def on_tree_select(self, event: Tree.NodeSelected) -> None:
        if event.node.data and isinstance(event.node.data, Endpoint):
            self._select_endpoint(event.node.data)

    def _select_endpoint(self, ep: Endpoint) -> None:
        self.selected_endpoint = ep

        # Update info panel
        color = METHOD_COLORS.get(ep.method, "white")
        info_lines = [
            f"[bold {color}]{ep.method}[/] {ep.path}",
        ]
        if ep.summary:
            info_lines.append(f"[dim]{ep.summary}[/]")
        if ep.description:
            info_lines.append(f"{ep.description[:200]}")
        self.query_one("#endpoint-info", Static).update("\n".join(info_lines))

        # Build parameter inputs
        self._build_param_inputs(ep)

        # Set body editor
        body_editor = self.query_one("#body-editor", TextArea)
        if ep.request_body_schema and ep.request_body_content_type == "application/json":
            example = generate_example(ep.request_body_schema, {})
            body_editor.text = json.dumps(example, indent=2)
        else:
            body_editor.text = ""

    def _build_param_inputs(self, ep: Endpoint) -> None:
        container = self.query_one("#params-container", Static)
        all_params = ep.path_params + ep.query_params
        if not all_params:
            container.update("[dim]No parameters[/]")
            # Remove old dynamic inputs
            for old in self.query(".dynamic-param"):
                old.remove()
            return

        lines = []
        for old in self.query(".dynamic-param"):
            old.remove()

        for p in all_params:
            req = "*" if p.required else ""
            default_hint = f" (default: {p.default})" if p.default else ""
            lines.append(f"  [bold]{p.name}[/]{req} [{p.location}] {p.schema_type}{default_hint}")
        container.update("Parameters:\n" + "\n".join(lines))

    # -----------------------------------------------------------------------
    # Actions
    # -----------------------------------------------------------------------

    def action_switch_env(self) -> None:
        self.push_screen(EnvScreen(), self._on_env_selected)

    def _on_env_selected(self, env: str | None) -> None:
        if env and env != self.current_env:
            self.current_env = env
            self._update_client()
            self._auto_login_and_load()

    def action_switch_service(self) -> None:
        self.push_screen(ServiceScreen(), self._on_service_selected)

    def _on_service_selected(self, service: str | None) -> None:
        if service and service != self.current_service:
            self.current_service = service
            self._update_client()
            self._auto_login_and_load()

    def action_login(self) -> None:
        self.push_screen(LoginScreen(), self._on_login)

    @work(exclusive=True)
    async def _on_login(self, result: tuple[str, str] | None) -> None:
        if not result:
            return
        username, password = result
        self._log(f"Authenticating as {username}...")
        resp = await self.api_client.authenticate(username, password)
        if resp.ok:
            set_env_creds(self.current_env, username, password)
            self._log(f"Authenticated and credentials saved ({resp.elapsed_ms:.0f}ms)")
        else:
            body_preview = resp.body[:300] if resp.body else resp.error
            self._log(f"[red]Login failed:[/] {resp.status_code} {body_preview}")

    def action_send_request(self) -> None:
        self._do_send()

    @on(Button.Pressed, "#btn-send")
    def on_send_pressed(self) -> None:
        self._do_send()

    @on(Button.Pressed, "#btn-reset")
    def on_reset_pressed(self) -> None:
        if self.selected_endpoint and self.selected_endpoint.request_body_schema:
            example = generate_example(self.selected_endpoint.request_body_schema, {})
            self.query_one("#body-editor", TextArea).text = json.dumps(example, indent=2)

    @work(exclusive=True)
    async def _do_send(self) -> None:
        ep = self.selected_endpoint
        if not ep:
            self._log("[yellow]No endpoint selected[/]")
            return

        if not self.api_client.auth.authenticated:
            # Skip auth check for /token and /health
            if "token" not in ep.path and "health" not in ep.path:
                self._log("[yellow]Not authenticated. Press 'l' to login.[/]")
                return

        # Build path with param substitution
        path = ep.path
        query_params: dict[str, str] = {}

        # Parse path params from the body editor or use defaults
        # For simplicity, prompt inline: extract {param} from path
        path_param_names = re.findall(r"\{(\w+)\}", path)
        if path_param_names:
            # Try to get values from the info shown - for now use a simple approach
            # The user can edit the path in the body
            pass

        body_text = self.query_one("#body-editor", TextArea).text.strip()

        # Parse the body
        json_body = None
        form_body = None
        request_config: dict = {}

        if body_text:
            try:
                parsed = json.loads(body_text)
            except json.JSONDecodeError as exc:
                self._log(f"[red]Invalid JSON in body editor:[/] {exc}")
                return

            # Check if user provided _path_params or _query_params in the body
            if isinstance(parsed, dict):
                if "_path_params" in parsed:
                    for k, v in parsed.pop("_path_params").items():
                        path = path.replace(f"{{{k}}}", str(v))
                if "_query_params" in parsed:
                    query_params = {
                        k: str(v) for k, v in parsed.pop("_query_params").items()
                    }
                # If only meta-keys were present and body is now empty, don't send body
                if parsed or ep.request_body_schema:
                    if ep.request_body_content_type == "application/x-www-form-urlencoded":
                        form_body = {k: str(v) for k, v in parsed.items()}
                    else:
                        json_body = parsed

        # Check for unresolved path params
        remaining = re.findall(r"\{(\w+)\}", path)
        if remaining:
            self._log(
                f'[yellow]Path has unresolved params: {remaining}. '
                f'Add "_path_params": {{"{remaining[0]}": "value"}} to the body JSON.[/]'
            )
            return

        self._log(f"[bold]{ep.method}[/] {path} ...")
        resp = await self.api_client.request(
            method=ep.method,
            path=path,
            query_params=query_params or None,
            json_body=json_body,
            form_body=form_body,
        )

        self._show_response(resp)

    def _show_response(self, resp: APIResponse) -> None:
        status_color = "green" if resp.ok else "red"
        header = self.query_one("#response-header", Static)
        if resp.error:
            header.update(f"[red]Error:[/] {resp.error} ({resp.elapsed_ms:.0f}ms)")
            return
        header.update(
            f"[{status_color}]{resp.status_code}[/] ({resp.elapsed_ms:.0f}ms) "
            f"[dim]{len(resp.body)} bytes[/]"
        )

        log = self.query_one("#response-log", RichLog)
        log.clear()

        # Try to pretty-print JSON
        try:
            parsed = json.loads(resp.body)
            log.write(json.dumps(parsed, indent=2, ensure_ascii=False))
        except (json.JSONDecodeError, ValueError):
            log.write(resp.body[:5000] if resp.body else "(empty)")

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _current_base_url(self) -> str:
        urls = BACKEND_URLS if self.current_service == "backend" else ORACLE_URLS
        return urls[self.current_env]

    def _update_client(self) -> None:
        self.api_client = APIClient(base_url=self._current_base_url())
        self.sub_title = f"{self.current_env} | {self.current_service}"
        self.query_one("#sidebar-header", Static).update(self._sidebar_header_text())

    def _sidebar_header_text(self) -> str:
        auth = (
            f"[green]{self.api_client.auth.username}[/]"
            if self.api_client.auth.authenticated
            else "[dim]not logged in[/]"
        )
        return (
            f"[bold]{self.current_env}[/] | {self.current_service}\n"
            f"{self._current_base_url()}\n"
            f"{auth}"
        )

    def _log(self, msg: str) -> None:
        log = self.query_one("#response-log", RichLog)
        log.write(msg)
        # Also update sidebar header (auth status may have changed)
        self.query_one("#sidebar-header", Static).update(self._sidebar_header_text())


def main() -> None:
    app = ThemaApp()
    app.run()


if __name__ == "__main__":
    main()
