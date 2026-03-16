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
    Collapsible,
    Footer,
    Header,
    Input,
    Label,
    OptionList,
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
    load_state,
    save_state,
    set_env_creds,
)
from tui.schema import APISchema, Endpoint, fetch_schema, generate_example

# ---------------------------------------------------------------------------
# Login modal
# ---------------------------------------------------------------------------


class LoginScreen(ModalScreen[tuple[str, str] | None]):
    CSS = """
    LoginScreen { align: center middle; }
    #login-box {
        width: 60; height: auto; max-height: 20;
        border: thick $accent; background: $surface; padding: 1 2;
    }
    #login-box Label { margin-bottom: 1; }
    #login-box Input { margin-bottom: 1; }
    #login-buttons { height: auto; margin-top: 1; align-horizontal: right; }
    #login-buttons Button { margin-left: 1; }
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
        u = self.query_one("#login-username", Input).value.strip()
        p = self.query_one("#login-password", Input).value
        if u and p:
            self.dismiss((u, p))

    @on(Input.Submitted)
    def on_input_submitted(self) -> None:
        self.submit()


# ---------------------------------------------------------------------------
# Environment / Service selectors
# ---------------------------------------------------------------------------


class EnvScreen(ModalScreen[str | None]):
    CSS = """
    EnvScreen { align: center middle; }
    #env-box { width: 40; height: auto; max-height: 22;
               border: thick $accent; background: $surface; padding: 1 2; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="env-box"):
            yield Label("Select Environment")
            yield OptionList(*[Option(env, id=env) for env in ENVS], id="env-list")

    def on_mount(self) -> None:
        self.query_one("#env-list", OptionList).focus()

    @on(OptionList.OptionSelected, "#env-list")
    def on_select(self, event: OptionList.OptionSelected) -> None:
        self.dismiss(ENVS[event.option_index])


class ServiceScreen(ModalScreen[str | None]):
    CSS = """
    ServiceScreen { align: center middle; }
    #svc-box { width: 40; height: auto; border: thick $accent;
               background: $surface; padding: 1 2; }
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
# First-run setup wizard
# ---------------------------------------------------------------------------


class SetupScreen(ModalScreen[tuple[str, str]]):
    """First-run wizard: pick env and service."""

    CSS = """
    SetupScreen { align: center middle; }
    #setup-box {
        width: 64; height: auto; max-height: 26;
        border: thick $accent; background: $surface; padding: 1 2;
    }
    #setup-box Label { margin-bottom: 1; }
    #setup-buttons { height: auto; margin-top: 1; align-horizontal: right; }
    #setup-buttons Button { margin-left: 1; }
    """

    def compose(self) -> ComposeResult:
        with Vertical(id="setup-box"):
            yield Label("[bold]Welcome to Thema API Explorer[/]")
            yield Label(
                "Choose your environment and service to get started.\n"
                "You can login later with [bold]l[/].\n"
            )
            yield Label("Environment:")
            yield OptionList(
                *[Option(f"{env:14s} {BACKEND_URLS[env]}", id=env) for env in ENVS],
                id="setup-env",
            )
            yield Label("\nService:")
            yield OptionList(
                Option("backend", id="backend"),
                Option("oracle", id="oracle"),
                id="setup-svc",
            )
            with Horizontal(id="setup-buttons"):
                yield Button("Start", variant="primary", id="setup-go")

    def on_mount(self) -> None:
        env_list = self.query_one("#setup-env", OptionList)
        env_list.highlighted = ENVS.index("dev")
        env_list.focus()

    @on(Button.Pressed, "#setup-go")
    def go(self) -> None:
        self._submit()

    @on(OptionList.OptionSelected)
    def on_option_selected(self, event: OptionList.OptionSelected) -> None:
        # Move focus forward on selection
        if event.option_list.id == "setup-env":
            self.query_one("#setup-svc", OptionList).focus()

    def _submit(self) -> None:
        env_list = self.query_one("#setup-env", OptionList)
        svc_list = self.query_one("#setup-svc", OptionList)
        env_idx = env_list.highlighted if env_list.highlighted is not None else 1
        svc_idx = svc_list.highlighted if svc_list.highlighted is not None else 0
        self.dismiss((ENVS[env_idx], ["backend", "oracle"][svc_idx]))


# ---------------------------------------------------------------------------
# Param row widget
# ---------------------------------------------------------------------------


class ParamRow(Horizontal):
    DEFAULT_CSS = """
    ParamRow { height: auto; margin-bottom: 1; }
    ParamRow .param-label { width: 28; height: 3; padding: 1 1 0 0; }
    ParamRow .param-input { width: 1fr; }
    """

    def __init__(
        self,
        param_name: str,
        location: str,
        schema_type: str,
        required: bool,
        default: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)
        self.param_name = param_name
        self.location = location
        self.schema_type = schema_type
        self.required = required
        self.default = default

    def compose(self) -> ComposeResult:
        req = " [red]*[/]" if self.required else ""
        yield Static(
            f"[bold]{self.param_name}[/]{req}\n[dim]{self.location} | {self.schema_type}[/]",
            classes="param-label",
        )
        yield Input(
            placeholder=self.default or self.schema_type,
            value=self.default or "",
            id=f"param-{self.location}-{self.param_name}",
            classes="param-input",
        )


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
    #main-area { height: 1fr; }
    #sidebar { width: 44; min-width: 30; border-right: solid $accent; }
    #sidebar-header { height: auto; padding: 0 1; background: $boost; }
    #search-box { margin: 0 1; }
    #endpoint-tree { height: 1fr; }
    #detail-area { width: 1fr; }
    #endpoint-info {
        height: auto; max-height: 6; padding: 0 1;
        border-bottom: solid $accent;
    }
    #params-area {
        height: auto; max-height: 18; padding: 0 1;
        border-bottom: solid $accent;
    }
    #params-title { height: auto; padding: 0 0 1 0; }
    #request-section { height: auto; min-height: 4; max-height: 16; }
    #body-editor { height: auto; min-height: 3; max-height: 14; }
    #action-bar {
        height: auto; padding: 0 1;
        align-horizontal: left; border-bottom: solid $accent;
    }
    #action-bar Button { margin-right: 1; }
    #response-section { height: 1fr; min-height: 6; }
    #response-toolbar {
        height: auto; padding: 0 1; background: $boost;
    }
    #response-toolbar Button { margin-left: 1; }
    #response-status { width: 1fr; }
    #response-body { height: 1fr; min-height: 4; }
    """

    TITLE = "Thema API Explorer"
    BINDINGS = [
        Binding("e", "switch_env", "Env", priority=True),
        Binding("v", "switch_service", "Svc", priority=True),
        Binding("l", "login", "Login", priority=True),
        Binding("ctrl+r", "send_request", "Send", priority=True),
        Binding("/", "focus_search", "Search", priority=True),
        Binding("f", "format_body", "Format", priority=True),
        Binding("q", "quit", "Quit", priority=True),
    ]

    def __init__(self) -> None:
        super().__init__()
        state = load_state()
        self.current_env: str = state.get("env", "dev")
        self.current_service: str = state.get("service", "backend")
        base_url = (BACKEND_URLS if self.current_service == "backend" else ORACLE_URLS)[
            self.current_env
        ]
        self.api_client = APIClient(base_url=base_url)
        self.schema: APISchema | None = None
        self.selected_endpoint: Endpoint | None = None
        self._is_first_run: bool = not state.get("setup_done")
        self._last_response_raw: str = ""
        self._response_is_raw: bool = False
        self._last_request_summary: str = ""

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main-area"):
            with Vertical(id="sidebar"):
                yield Static(self._sidebar_header_text(), id="sidebar-header")
                yield Input(placeholder="Search endpoints... (/)", id="search-box")
                yield Tree("Endpoints", id="endpoint-tree")
            with Vertical(id="detail-area"):
                yield Static("Select an endpoint from the tree.", id="endpoint-info")
                with VerticalScroll(id="params-area"):
                    yield Static("", id="params-title")
                with Collapsible(title="Request Body", id="request-section"):
                    yield TextArea(
                        "", language="json", id="body-editor", theme="monokai"
                    )
                with Horizontal(id="action-bar"):
                    yield Button("Send (^R)", variant="primary", id="btn-send")
                    yield Button("Format (f)", variant="default", id="btn-format")
                    yield Button("Copy Req", variant="default", id="btn-copy-req")
                    yield Button("Reset", variant="default", id="btn-reset")
                with Collapsible(title="Response", id="response-section"):
                    with Horizontal(id="response-toolbar"):
                        yield Static("", id="response-status")
                        yield Button("Raw", variant="default", id="btn-raw-toggle")
                        yield Button("Copy", variant="default", id="btn-copy-resp")
                    yield TextArea(
                        "",
                        language="json",
                        id="response-body",
                        theme="monokai",
                        read_only=True,
                    )
        yield Footer()

    def on_mount(self) -> None:
        self.sub_title = f"{self.current_env} | {self.current_service}"
        if self._is_first_run:
            self.push_screen(SetupScreen(), self._on_setup_done)
        else:
            self._auto_login_and_load()

    def _on_setup_done(self, result: tuple[str, str]) -> None:
        env, service = result
        self.current_env = env
        self.current_service = service
        self._update_client()
        self._save_session_state()
        self._auto_login_and_load()

    # ------------------------------------------------------------------
    # Schema loading
    # ------------------------------------------------------------------

    @work(exclusive=True, group="init")
    async def _auto_login_and_load(self) -> None:
        creds = get_env_creds(self.current_env)
        if creds:
            username, password = creds
            self.notify(f"Authenticating as {username}...")
            resp = await self.api_client.authenticate(username, password)
            if resp.ok:
                self.notify(f"Authenticated ({resp.elapsed_ms:.0f}ms)", severity="information")
            else:
                self.notify(f"Auth failed: {resp.status_code}", severity="error")

        base_url = self._current_base_url()
        self.notify(f"Loading schema from {base_url}...")
        try:
            self.schema = await fetch_schema(base_url)
            self.notify(
                f"Loaded {len(self.schema.endpoints)} endpoints",
                severity="information",
            )
            self._populate_tree()
        except Exception as exc:
            self.notify(f"Failed to load schema: {exc}", severity="error")
        self.query_one("#sidebar-header", Static).update(self._sidebar_header_text())

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
                branch.add_leaf(f"[{color}]{ep.method:6s}[/] {ep.path}", data=ep)

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def action_focus_search(self) -> None:
        self.query_one("#search-box", Input).focus()

    @on(Input.Changed, "#search-box")
    def on_search_changed(self, event: Input.Changed) -> None:
        self._filter_tree(event.value.strip())

    def _filter_tree(self, query: str) -> None:
        if not self.schema:
            return
        tree = self.query_one("#endpoint-tree", Tree)
        tree.clear()
        tree.root.expand()

        if not query:
            for tag, endpoints in sorted(self.schema.by_tag().items()):
                branch = tree.root.add(tag, expand=False)
                for ep in endpoints:
                    color = METHOD_COLORS.get(ep.method, "white")
                    branch.add_leaf(
                        f"[{color}]{ep.method:6s}[/] {ep.path}", data=ep
                    )
            return

        scored: list[tuple[int, Endpoint]] = []
        q = query.lower()
        for ep in self.schema.endpoints:
            score = self._match_score(q, ep)
            if score > 0:
                scored.append((score, ep))
        scored.sort(key=lambda x: -x[0])

        from collections import OrderedDict

        groups: OrderedDict[str, list[Endpoint]] = OrderedDict()
        for _score, ep in scored:
            tag = ep.tags[0] if ep.tags else "other"
            groups.setdefault(tag, []).append(ep)

        for tag, endpoints in groups.items():
            branch = tree.root.add(tag, expand=True)
            for ep in endpoints:
                color = METHOD_COLORS.get(ep.method, "white")
                branch.add_leaf(
                    f"[{color}]{ep.method:6s}[/] {ep.path}", data=ep
                )

    @staticmethod
    def _match_score(query: str, ep: Endpoint) -> int:
        terms = query.split()
        path_lower = ep.path.lower()
        method_lower = ep.method.lower()
        summary_lower = ep.summary.lower()
        op_lower = ep.operation_id.lower()
        tag_str = " ".join(ep.tags).lower()

        for term in terms:
            if not (
                term in path_lower
                or term in method_lower
                or term in summary_lower
                or term in op_lower
                or term in tag_str
            ):
                return 0

        score = 0
        for term in terms:
            if term in path_lower:
                score += 10
            if term in method_lower:
                score += 5
            if term in summary_lower:
                score += 3
            if term in op_lower:
                score += 2
            if term in tag_str:
                score += 1
        return score

    # ------------------------------------------------------------------
    # Endpoint selection
    # ------------------------------------------------------------------

    @on(Tree.NodeSelected, "#endpoint-tree")
    def on_tree_select(self, event: Tree.NodeSelected) -> None:
        if event.node.data and isinstance(event.node.data, Endpoint):
            self._select_endpoint(event.node.data)

    def _select_endpoint(self, ep: Endpoint) -> None:
        self.selected_endpoint = ep

        color = METHOD_COLORS.get(ep.method, "white")
        info_parts = [f"[bold {color}]{ep.method}[/] {ep.path}"]
        if ep.summary:
            info_parts.append(f"[dim]{ep.summary}[/]")
        self.query_one("#endpoint-info", Static).update("\n".join(info_parts))

        # Params
        for old in self.query("ParamRow"):
            old.remove()

        all_params = ep.path_params + ep.query_params
        params_title = self.query_one("#params-title", Static)
        if all_params:
            params_title.update(f"[bold]Parameters[/] ({len(all_params)})")
            params_area = self.query_one("#params-area", VerticalScroll)
            for p in all_params:
                params_area.mount(
                    ParamRow(
                        param_name=p.name,
                        location=p.location,
                        schema_type=p.schema_type,
                        required=p.required,
                        default=p.default,
                    )
                )
        else:
            params_title.update("[dim]No parameters[/]")

        # Body
        body_editor = self.query_one("#body-editor", TextArea)
        if ep.request_body_schema and ep.request_body_content_type == "application/json":
            example = generate_example(ep.request_body_schema, {})
            body_editor.text = json.dumps(example, indent=2)
        else:
            body_editor.text = ""

        # Clear response
        self.query_one("#response-status", Static).update("")
        self.query_one("#response-body", TextArea).text = ""
        self._last_response_raw = ""

    # ------------------------------------------------------------------
    # Param collection
    # ------------------------------------------------------------------

    def _collect_params(self) -> tuple[dict[str, str], dict[str, str]]:
        path_params: dict[str, str] = {}
        query_params: dict[str, str] = {}
        for row in self.query("ParamRow"):
            assert isinstance(row, ParamRow)
            value = row.query_one(".param-input", Input).value.strip()
            if not value:
                continue
            if row.location == "path":
                path_params[row.param_name] = value
            elif row.location == "query":
                query_params[row.param_name] = value
        return path_params, query_params

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------

    def action_switch_env(self) -> None:
        self.push_screen(EnvScreen(), self._on_env_selected)

    def _on_env_selected(self, env: str | None) -> None:
        if env and env != self.current_env:
            self.current_env = env
            self._save_session_state()
            self._update_client()
            self._auto_login_and_load()

    def action_switch_service(self) -> None:
        self.push_screen(ServiceScreen(), self._on_service_selected)

    def _on_service_selected(self, service: str | None) -> None:
        if service and service != self.current_service:
            self.current_service = service
            self._save_session_state()
            self._update_client()
            self._auto_login_and_load()

    def action_login(self) -> None:
        self.push_screen(LoginScreen(), self._on_login)

    @work(exclusive=True)
    async def _on_login(self, result: tuple[str, str] | None) -> None:
        if not result:
            return
        username, password = result
        self.notify(f"Authenticating as {username}...")
        resp = await self.api_client.authenticate(username, password)
        if resp.ok:
            set_env_creds(self.current_env, username, password)
            self.notify("Authenticated and credentials saved", severity="information")
        else:
            self.notify(f"Login failed: {resp.status_code}", severity="error")
        self.query_one("#sidebar-header", Static).update(self._sidebar_header_text())

    # -- Format JSON body --

    def action_format_body(self) -> None:
        self._format_body()

    @on(Button.Pressed, "#btn-format")
    def on_format_pressed(self) -> None:
        self._format_body()

    def _format_body(self) -> None:
        editor = self.query_one("#body-editor", TextArea)
        text = editor.text.strip()
        if not text:
            return
        try:
            parsed = json.loads(text)
            editor.text = json.dumps(parsed, indent=2, ensure_ascii=False)
            self.notify("JSON formatted", severity="information")
        except json.JSONDecodeError as exc:
            self.notify(f"Invalid JSON: {exc}", severity="error")

    # -- Copy --

    @on(Button.Pressed, "#btn-copy-req")
    def on_copy_req(self) -> None:
        text = self._build_request_summary()
        self.copy_to_clipboard(text)
        self.notify("Request copied to clipboard")

    @on(Button.Pressed, "#btn-copy-resp")
    def on_copy_resp(self) -> None:
        text = self._last_response_raw
        if text:
            self.copy_to_clipboard(text)
            self.notify("Response copied to clipboard")
        else:
            self.notify("No response to copy", severity="warning")

    def _build_request_summary(self) -> str:
        """Build a copyable request summary (curl-style)."""
        ep = self.selected_endpoint
        if not ep:
            return ""
        path_params, query_params = self._collect_params()
        server_path = self.schema.server_path if self.schema else ""
        path = f"{server_path}{ep.path}"
        for name in re.findall(r"\{(\w+)\}", path):
            if name in path_params:
                path = path.replace(f"{{{name}}}", path_params[name])

        url = f"{self.api_client.base_url}{path}"
        if query_params:
            qs = "&".join(f"{k}={v}" for k, v in query_params.items())
            url = f"{url}?{qs}"

        body_text = self.query_one("#body-editor", TextArea).text.strip()
        parts = [f"curl -X {ep.method} '{url}'"]
        parts.append("  -H 'Content-Type: application/json'")
        if self.api_client.auth.authenticated:
            parts.append(f"  -H 'Authorization: Bearer {self.api_client.auth.access_token}'")
        if body_text:
            escaped = body_text.replace("'", "'\\''")
            parts.append(f"  -d '{escaped}'")
        return " \\\n".join(parts)

    # -- Raw / Render toggle --

    @on(Button.Pressed, "#btn-raw-toggle")
    def on_raw_toggle(self) -> None:
        if not self._last_response_raw:
            return
        self._response_is_raw = not self._response_is_raw
        btn = self.query_one("#btn-raw-toggle", Button)
        resp_body = self.query_one("#response-body", TextArea)
        if self._response_is_raw:
            btn.label = "Render"
            resp_body.text = self._last_response_raw
            resp_body.language = None
        else:
            btn.label = "Raw"
            try:
                parsed = json.loads(self._last_response_raw)
                resp_body.text = json.dumps(parsed, indent=2, ensure_ascii=False)
                resp_body.language = "json"
            except (json.JSONDecodeError, ValueError):
                resp_body.text = self._last_response_raw
                resp_body.language = None

    # -- Send --

    def action_send_request(self) -> None:
        self._do_send()

    @on(Button.Pressed, "#btn-send")
    def on_send_pressed(self) -> None:
        self._do_send()

    @on(Button.Pressed, "#btn-reset")
    def on_reset_pressed(self) -> None:
        if not self.selected_endpoint:
            return
        ep = self.selected_endpoint
        editor = self.query_one("#body-editor", TextArea)
        if ep.request_body_schema and ep.request_body_content_type == "application/json":
            example = generate_example(ep.request_body_schema, {})
            editor.text = json.dumps(example, indent=2)
        else:
            editor.text = ""
        for row in self.query("ParamRow"):
            assert isinstance(row, ParamRow)
            row.query_one(".param-input", Input).value = row.default or ""

    @work(exclusive=True)
    async def _do_send(self) -> None:
        ep = self.selected_endpoint
        if not ep:
            self.notify("No endpoint selected", severity="warning")
            return

        if not self.api_client.auth.authenticated:
            if "token" not in ep.path and "health" not in ep.path:
                self.notify("Not authenticated. Press 'l' to login.", severity="warning")
                return

        # Auto-format body before sending
        editor = self.query_one("#body-editor", TextArea)
        body_text = editor.text.strip()
        if body_text:
            try:
                parsed_check = json.loads(body_text)
                editor.text = json.dumps(parsed_check, indent=2, ensure_ascii=False)
            except json.JSONDecodeError as exc:
                self.notify(f"Invalid JSON body: {exc}", severity="error")
                return

        path_params, query_params = self._collect_params()

        server_path = self.schema.server_path if self.schema else ""
        path = f"{server_path}{ep.path}"
        for name in re.findall(r"\{(\w+)\}", path):
            if name in path_params:
                path = path.replace(f"{{{name}}}", path_params[name])

        missing = re.findall(r"\{(\w+)\}", path)
        if missing:
            self.notify(
                f"Missing path params: {', '.join(missing)}", severity="warning"
            )
            return

        json_body = None
        form_body = None
        body_text = editor.text.strip()
        if body_text:
            parsed = json.loads(body_text)
            if ep.request_body_content_type == "application/x-www-form-urlencoded":
                form_body = {k: str(v) for k, v in parsed.items()}
            else:
                json_body = parsed

        self.notify(f"{ep.method} {path}...")
        resp = await self.api_client.request(
            method=ep.method,
            path=path,
            query_params=query_params or None,
            json_body=json_body,
            form_body=form_body,
        )
        self._show_response(resp)

    def _show_response(self, resp: APIResponse) -> None:
        status = self.query_one("#response-status", Static)
        resp_body = self.query_one("#response-body", TextArea)
        self._response_is_raw = False
        self.query_one("#btn-raw-toggle", Button).label = "Raw"

        if resp.error:
            status.update(f"[red]Error[/] ({resp.elapsed_ms:.0f}ms)")
            resp_body.text = resp.error
            resp_body.language = None
            self._last_response_raw = resp.error
            return

        color = "green" if resp.ok else "red"
        status.update(
            f"[{color}]{resp.status_code}[/] ({resp.elapsed_ms:.0f}ms) "
            f"[dim]{len(resp.body)} bytes[/]"
        )

        self._last_response_raw = resp.body
        try:
            parsed = json.loads(resp.body)
            resp_body.text = json.dumps(parsed, indent=2, ensure_ascii=False)
            resp_body.language = "json"
        except (json.JSONDecodeError, ValueError):
            resp_body.text = resp.body[:10000] if resp.body else "(empty)"
            resp_body.language = None

        # Expand response section if collapsed
        resp_section = self.query_one("#response-section", Collapsible)
        resp_section.collapsed = False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

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

    def _save_session_state(self) -> None:
        save_state({
            "env": self.current_env,
            "service": self.current_service,
            "setup_done": True,
        })

    def _log(self, msg: str) -> None:
        self.notify(msg)


def main() -> None:
    app = ThemaApp()
    app.run()


if __name__ == "__main__":
    main()
