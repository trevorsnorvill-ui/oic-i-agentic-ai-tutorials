"""
MCP Proxy Route

Forwards product tool calls to the MCP server on behalf of the authenticated user.
Performs a JWT Bearer token exchange (RFC 8693) so the outgoing token has the
MCP server's client ID as its audience — satisfying the MCP's JWT verification.

Uses the fastmcp Client which correctly speaks the SSE transport protocol.
"""

import logging
import os
from typing import Any

import requests as _requests
from fastapi import APIRouter, Header, HTTPException, Query
from fastmcp import Client
from fastmcp.client.transports import SSETransport
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

MCP_URL = os.environ.get(
    "MCP_INTERNAL_URL",
    "http://mcp:8080",
)


def _exchange_token_for_mcp(user_token: str) -> str:
    """
    Exchange the user's backend-app access token for one whose audience is the
    agent app (IBM_VERIFY_AGENT_CLIENT_ID).  The MCP server's JWTVerifier checks
    that the token audience matches JWT_AUDIENCE=<agent client id>.

    Uses the RFC 8693 / IBM Verify JWT Bearer grant:
      grant_type = urn:ietf:params:oauth:grant-type:jwt-bearer
      assertion  = <user access token>
      client_id  = <agent client id>   (no secret needed for public client)
      scope      = openid
    """
    agent_client_id = settings.IBM_VERIFY_AGENT_CLIENT_ID
    token_url = settings.IBM_VERIFY_TOKEN_URL

    if not agent_client_id or not token_url:
        logger.warning("IBM_VERIFY_AGENT_CLIENT_ID or TOKEN_URL not set — forwarding token as-is")
        return user_token

    try:
        resp = _requests.post(
            token_url,
            data={
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": user_token,
                "client_id": agent_client_id,
                "scope": "openid",
            },
            timeout=10,
        )
    except _requests.exceptions.Timeout:
        raise HTTPException(status_code=504, detail="IBM Verify token exchange timed out")
    except _requests.exceptions.RequestException as e:
        raise HTTPException(status_code=502, detail=f"IBM Verify token exchange failed: {e}")

    if not resp.ok:
        logger.warning(f"Token exchange failed {resp.status_code}: {resp.text[:300]}")
        raise HTTPException(
            status_code=401,
            detail=f"Token exchange failed ({resp.status_code}): {resp.json().get('error_description', resp.text[:200])}",
        )

    exchanged = resp.json().get("access_token")
    if not exchanged:
        raise HTTPException(status_code=502, detail="Token exchange returned no access_token")

    logger.debug("Token exchange succeeded — using agent-scoped token for MCP call")
    return exchanged


async def _call_mcp_tool(tool: str, args: dict, authorization: str) -> Any:
    """
    Call an MCP tool via the fastmcp Client (SSE transport).
    The user's token is first exchanged for an agent-scoped token (aud=agent
    client id) so the MCP server's JWT verifier accepts it.
    """
    # Strip "Bearer " prefix to get the raw token for exchange
    raw_token = authorization.removeprefix("Bearer ").removeprefix("bearer ").strip()
    mcp_token = _exchange_token_for_mcp(raw_token)
    headers = {"Authorization": f"Bearer {mcp_token}"}
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
