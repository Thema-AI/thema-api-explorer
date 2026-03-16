"""OpenAPI schema fetcher and parser."""

from __future__ import annotations

from dataclasses import dataclass, field

import httpx


@dataclass
class Parameter:
    name: str
    location: str  # path, query, header, cookie
    required: bool
    schema_type: str
    description: str = ""
    default: str | None = None


@dataclass
class Endpoint:
    method: str
    path: str
    summary: str
    description: str
    tags: list[str]
    operation_id: str
    parameters: list[Parameter]
    request_body_schema: dict | None
    request_body_content_type: str
    response_schema: dict | None

    @property
    def display_label(self) -> str:
        return f"{self.method:6s} {self.path}"

    @property
    def path_params(self) -> list[Parameter]:
        return [p for p in self.parameters if p.location == "path"]

    @property
    def query_params(self) -> list[Parameter]:
        return [p for p in self.parameters if p.location == "query"]


@dataclass
class APISchema:
    title: str
    version: str
    server_path: str = ""  # e.g. "/v1" — prefix for all endpoint paths
    endpoints: list[Endpoint] = field(default_factory=list)

    def by_tag(self) -> dict[str, list[Endpoint]]:
        groups: dict[str, list[Endpoint]] = {}
        for ep in self.endpoints:
            for tag in ep.tags or ["other"]:
                groups.setdefault(tag, []).append(ep)
        return groups


def _resolve_ref(ref: str, root: dict) -> dict:
    """Resolve a $ref pointer like '#/components/schemas/Foo'."""
    parts = ref.lstrip("#/").split("/")
    node = root
    for part in parts:
        node = node.get(part, {})
    return node


def _resolve_schema(schema: dict, root: dict, depth: int = 0) -> dict:
    """Recursively resolve $ref in a schema, up to a depth limit."""
    if depth > 8:
        return schema
    if "$ref" in schema:
        resolved = _resolve_ref(schema["$ref"], root)
        return _resolve_schema(resolved, root, depth + 1)
    if "allOf" in schema:
        merged: dict = {}
        merged_props: dict = {}
        merged_required: list = []
        for sub in schema["allOf"]:
            resolved_sub = _resolve_schema(sub, root, depth + 1)
            merged_props.update(resolved_sub.get("properties", {}))
            merged_required.extend(resolved_sub.get("required", []))
            merged.update(resolved_sub)
        merged["properties"] = merged_props
        if merged_required:
            merged["required"] = merged_required
        merged.pop("allOf", None)
        return merged
    if "anyOf" in schema:
        # Take the first non-null option
        for sub in schema["anyOf"]:
            resolved_sub = _resolve_schema(sub, root, depth + 1)
            if resolved_sub.get("type") != "null":
                return resolved_sub
        return schema
    # Resolve properties recursively
    if "properties" in schema:
        resolved_props = {}
        for key, val in schema["properties"].items():
            resolved_props[key] = _resolve_schema(val, root, depth + 1)
        schema = {**schema, "properties": resolved_props}
    if "items" in schema:
        schema = {**schema, "items": _resolve_schema(schema["items"], root, depth + 1)}
    return schema


def generate_example(schema: dict, root: dict, depth: int = 0) -> object:
    """Generate an example value from a JSON schema."""
    if depth > 6:
        return None
    schema = _resolve_schema(schema, root, depth)

    if "default" in schema:
        return schema["default"]
    if "example" in schema:
        return schema["example"]

    schema_type = schema.get("type", "object")
    if isinstance(schema_type, list):
        schema_type = next((t for t in schema_type if t != "null"), "string")

    if schema_type == "string":
        fmt = schema.get("format", "")
        if fmt == "uuid":
            return "00000000-0000-0000-0000-000000000000"
        if fmt == "email":
            return "user@example.com"
        if fmt in ("date-time", "date"):
            return "2024-01-01"
        if "enum" in schema:
            return schema["enum"][0]
        return ""
    if schema_type == "integer":
        return 0
    if schema_type == "number":
        return 0.0
    if schema_type == "boolean":
        return False
    if schema_type == "array":
        items = schema.get("items", {})
        return [generate_example(items, root, depth + 1)] if items else []
    if schema_type == "object":
        props = schema.get("properties", {})
        if not props:
            return {}
        result = {}
        for key, val in props.items():
            result[key] = generate_example(val, root, depth + 1)
        return result
    return None


async def fetch_schema(base_url: str) -> APISchema:
    """Fetch and parse the OpenAPI schema from a running API."""
    async with httpx.AsyncClient(timeout=30, verify=False) as client:
        resp = await client.get(f"{base_url}/v1/openapi.json")
        resp.raise_for_status()
        raw = resp.json()

    endpoints: list[Endpoint] = []
    for path, methods in raw.get("paths", {}).items():
        for method, details in methods.items():
            if method not in ("get", "post", "put", "patch", "delete"):
                continue

            params: list[Parameter] = []
            for p in details.get("parameters", []):
                p_schema = _resolve_schema(p.get("schema", {}), raw)
                params.append(
                    Parameter(
                        name=p["name"],
                        location=p["in"],
                        required=p.get("required", False),
                        schema_type=p_schema.get("type", "string"),
                        description=p.get("description", ""),
                        default=str(p_schema.get("default", "")) if "default" in p_schema else None,
                    )
                )

            body_schema = None
            content_type = "application/json"
            if "requestBody" in details:
                content = details["requestBody"].get("content", {})
                if "application/json" in content:
                    body_schema = _resolve_schema(
                        content["application/json"].get("schema", {}), raw
                    )
                    content_type = "application/json"
                elif "application/x-www-form-urlencoded" in content:
                    body_schema = _resolve_schema(
                        content["application/x-www-form-urlencoded"].get("schema", {}),
                        raw,
                    )
                    content_type = "application/x-www-form-urlencoded"

            resp_schema = None
            ok_resp = details.get("responses", {}).get("200", {})
            ok_content = ok_resp.get("content", {}).get("application/json", {})
            if ok_content:
                resp_schema = _resolve_schema(ok_content.get("schema", {}), raw)

            endpoints.append(
                Endpoint(
                    method=method.upper(),
                    path=path,
                    summary=details.get("summary", ""),
                    description=details.get("description", ""),
                    tags=details.get("tags", ["other"]),
                    operation_id=details.get("operationId", ""),
                    parameters=params,
                    request_body_schema=body_schema,
                    request_body_content_type=content_type,
                    response_schema=resp_schema,
                )
            )

    # Sort by path then method for consistent display
    endpoints.sort(key=lambda e: (e.path, e.method))

    # Extract server path prefix (e.g. "/v1") from the servers field
    server_path = ""
    servers = raw.get("servers", [])
    if servers:
        server_path = servers[0].get("url", "").rstrip("/")

    return APISchema(
        title=raw.get("info", {}).get("title", "Thema API"),
        version=raw.get("info", {}).get("version", ""),
        server_path=server_path,
        endpoints=endpoints,
    )
