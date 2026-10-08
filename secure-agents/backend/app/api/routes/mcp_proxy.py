"""
MCP Proxy Route

Forwards product tool calls to the MCP server on behalf of the authenticated user,
passing the user's IBM Verify access token so the MCP server can obtain scoped
Vault/MongoDB credentials for that user.

Uses the fastmcp Client which correctly speaks the SSE transport protocol.
"""

import logging
import os
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from fastmcp import Client
from fastmcp.client.transports import SSETransport
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter()

MCP_URL = os.environ.get(
    "MCP_INTERNAL_URL",
    "http://mcp:8080",
)


async def _call_mcp_tool(tool: str, args: dict, authorization: str) -> Any:
    """
    Call an MCP tool via the fastmcp Client (SSE transport).
    The user's IBM Verify Bearer token is forwarded so the MCP server
    can verify it and obtain scoped Vault/MongoDB credentials.
    """
    headers = {"Authorization": authorization}
    transport = SSETransport(f"{MCP_URL}/sse", headers=headers)

    try:
        async with Client(transport) as client:
            result = await client.call_tool(tool, args)
    except Exception as e:
        msg = str(e)
        if "401" in msg or "Unauthorized" in msg:
            raise HTTPException(
                status_code=401,
                detail="MCP server rejected token — ensure your IBM Verify access token is valid",
            )
        if "403" in msg or "Forbidden" in msg:
            raise HTTPException(status_code=403, detail="Insufficient permissions for this operation")
        if "ConnectionRefusedError" in msg or "ConnectError" in msg:
            raise HTTPException(status_code=503, detail="MCP server unreachable")
        raise HTTPException(status_code=502, detail=f"MCP error: {msg[:200]}")

    # fastmcp returns a list of TextContent / other content items
    if result and hasattr(result[0], "text"):
        import json
        try:
            return json.loads(result[0].text)
        except Exception:
            return result[0].text

    return {}


# ---------------------------------------------------------------------------
# Product endpoints
# ---------------------------------------------------------------------------

@router.get("/mcp/products")
async def list_products(
    limit: int = Query(10, ge=1, le=100),
    authorization: str = Header(...),
):
    """List all products — proxied to MCP with the user's JWT."""
    return await _call_mcp_tool("list_products", {"limit": limit}, authorization)


@router.get("/mcp/products/search")
async def search_products(
    name: str = Query(...),
    exact_match: bool = Query(False),
    authorization: str = Header(...),
):
    """Search products by name — proxied to MCP with the user's JWT."""
    return await _call_mcp_tool("search_products", {"name": name, "exact_match": exact_match}, authorization)


@router.get("/mcp/products/sort")
async def sort_products(
    ascending: bool = Query(True),
    limit: int = Query(10, ge=1, le=100),
    authorization: str = Header(...),
):
    """Sort products by price — proxied to MCP with the user's JWT."""
    return await _call_mcp_tool("sort_products_by_price", {"ascending": ascending, "limit": limit}, authorization)


class ProductCreate(BaseModel):
    name: str
    price: float


@router.post("/mcp/products")
async def create_product(
    product: ProductCreate,
    authorization: str = Header(...),
):
    """Create a product — proxied to MCP with the user's JWT."""
    return await _call_mcp_tool("create_product", {"product": product.model_dump()}, authorization)


class ProductUpdate(BaseModel):
    name: str
    price: float


@router.put("/mcp/products/{product_id}")
async def update_product(
    product_id: str,
    product: ProductUpdate,
    authorization: str = Header(...),
):
    """Update a product — proxied to MCP with the user's JWT."""
    return await _call_mcp_tool(
        "update_product",
        {"product_id": product_id, "product": product.model_dump()},
        authorization,
    )


@router.delete("/mcp/products/{product_id}")
async def delete_product(
    product_id: str,
    authorization: str = Header(...),
):
    """Delete a product — proxied to MCP with the user's JWT."""
    return await _call_mcp_tool("delete_product", {"product_id": product_id}, authorization)
