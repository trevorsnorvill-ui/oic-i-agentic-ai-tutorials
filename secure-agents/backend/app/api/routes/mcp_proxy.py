"""
MCP Proxy Route

Forwards product tool calls to the MCP server on behalf of the authenticated user,
passing the user's IBM Verify access token so the MCP server can obtain scoped
Vault/MongoDB credentials for that user.
"""

import logging
import os
from typing import Any, Optional

import requests
from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

MCP_URL = os.environ.get(
    "MCP_INTERNAL_URL",
    "http://mcp:8001",
)


def _mcp_headers(authorization: str) -> dict:
    return {
        "Authorization": authorization,
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }


def _call_mcp_tool(tool: str, args: dict, authorization: str) -> Any:
    """
    Call an MCP tool via the MCP server's HTTP+SSE endpoint.
    FastMCP exposes tools at POST /messages/ with JSON-RPC 2.0 payload.
    """
    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool,
            "arguments": args,
        },
    }

    try:
        resp = requests.post(
            f"{MCP_URL}/messages/",
            json=payload,
            headers=_mcp_headers(authorization),
            timeout=30,
        )
    except requests.exceptions.ConnectionError:
        raise HTTPException(status_code=503, detail="MCP server unreachable")
    except requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="MCP server timed out")

    if resp.status_code == 401:
        raise HTTPException(status_code=401, detail="MCP server rejected token — ensure your IBM Verify access token is valid")
    if resp.status_code == 403:
        raise HTTPException(status_code=403, detail="Insufficient permissions for this operation")
    if not resp.ok:
        raise HTTPException(status_code=resp.status_code, detail=f"MCP error: {resp.text[:200]}")

    data = resp.json()
    if "error" in data:
        raise HTTPException(status_code=400, detail=data["error"].get("message", "MCP tool error"))

    # Unwrap JSON-RPC result → MCP content → actual data
    result = data.get("result", {})
    content = result.get("content", [])
    if content and isinstance(content, list):
        first = content[0]
        if first.get("type") == "text":
            import json
            try:
                return json.loads(first["text"])
            except Exception:
                return first["text"]
    return result


# ---------------------------------------------------------------------------
# Product endpoints
# ---------------------------------------------------------------------------

@router.get("/mcp/products")
def list_products(
    limit: int = Query(10, ge=1, le=100),
    authorization: str = Header(...),
):
    """List all products — proxied to MCP with the user's JWT."""
    return _call_mcp_tool("list_products", {"limit": limit}, authorization)


@router.get("/mcp/products/search")
def search_products(
    name: str = Query(...),
    exact_match: bool = Query(False),
    authorization: str = Header(...),
):
    """Search products by name — proxied to MCP with the user's JWT."""
    return _call_mcp_tool("search_products", {"name": name, "exact_match": exact_match}, authorization)


@router.get("/mcp/products/sort")
def sort_products(
    ascending: bool = Query(True),
    limit: int = Query(10, ge=1, le=100),
    authorization: str = Header(...),
):
    """Sort products by price — proxied to MCP with the user's JWT."""
    return _call_mcp_tool("sort_products_by_price", {"ascending": ascending, "limit": limit}, authorization)


class ProductCreate(BaseModel):
    name: str
    price: float


@router.post("/mcp/products")
def create_product(
    product: ProductCreate,
    authorization: str = Header(...),
):
    """Create a product — proxied to MCP with the user's JWT."""
    return _call_mcp_tool("create_product", {"product": product.model_dump()}, authorization)


class ProductUpdate(BaseModel):
    name: str
    price: float


@router.put("/mcp/products/{product_id}")
def update_product(
    product_id: str,
    product: ProductUpdate,
    authorization: str = Header(...),
):
    """Update a product — proxied to MCP with the user's JWT."""
    return _call_mcp_tool(
        "update_product",
        {"product_id": product_id, "product": product.model_dump()},
        authorization,
    )


@router.delete("/mcp/products/{product_id}")
def delete_product(
    product_id: str,
    authorization: str = Header(...),
):
    """Delete a product — proxied to MCP with the user's JWT."""
    return _call_mcp_tool("delete_product", {"product_id": product_id}, authorization)
