#!/usr/bin/env python3
"""
Outline MCP Server
Exposes Outline documentation wiki through Model Context Protocol
Enables agents to search, read, create, and update documentation
"""

import os
import json
import logging
from typing import Any, Optional, Dict, List
from functools import wraps

import httpx
from pydantic import BaseModel, Field
from mcp.server import Server
from mcp.types import Tool, TextContent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outline-mcp")


class OutlineConfig(BaseModel):
    """Configuration from environment variables"""
    api_token: str
    base_url: str = Field(default="http://outline.cortex-knowledge.svc.cluster.local:3000")
    timeout: int = Field(default=30)

    @classmethod
    def from_env(cls) -> "OutlineConfig":
        """Load configuration from environment variables"""
        return cls(
            api_token=os.getenv("OUTLINE_API_TOKEN", ""),
            base_url=os.getenv("OUTLINE_BASE_URL", "http://outline.cortex-knowledge.svc.cluster.local:3000"),
            timeout=int(os.getenv("OUTLINE_TIMEOUT", "30"))
        )


class OutlineClient:
    """HTTP client for Outline API"""

    def __init__(self, config: OutlineConfig):
        self.config = config
        self.base_url = config.base_url.rstrip("/")
        self.api_url = f"{self.base_url}/api"
        self.client = httpx.Client(
            timeout=config.timeout,
            headers={
                "Authorization": f"Bearer {config.api_token}",
                "Content-Type": "application/json"
            }
        )
        logger.info(f"Outline client initialized: {self.base_url}")

    def post(self, endpoint: str, data: Optional[dict] = None) -> dict:
        """Execute POST request"""
        url = f"{self.api_url}{endpoint}"
        logger.info(f"POST {url}")
        try:
            response = self.client.post(url, json=data)
            response.raise_for_status()
            return response.json().get("data", {})
        except httpx.HTTPError as e:
            logger.error(f"HTTP error: {e}")
            raise

    def close(self):
        """Close HTTP client"""
        self.client.close()


# Initialize server and client
app = Server("outline-mcp")
config = OutlineConfig.from_env()
outline_client = OutlineClient(config)


def handle_errors(func):
    """Decorator to handle errors and return formatted responses"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            return [TextContent(
                type="text",
                text=json.dumps({
                    "error": str(e),
                    "function": func.__name__
                }, indent=2)
            )]
    return wrapper


@app.list_tools()
async def list_tools() -> list[Tool]:
    """List all available Outline tools"""
    return [
        Tool(
            name="search_docs",
            description="Search Outline documentation by query string. Returns matching documents with titles, URLs, and snippets.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query string"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 10)",
                        "default": 10
                    }
                },
                "required": ["query"]
            }
        ),
        Tool(
            name="get_document",
            description="Get full content of a document by ID. Returns document title, content (markdown), and metadata.",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "Document ID"
                    }
                },
                "required": ["document_id"]
            }
        ),
        Tool(
            name="create_document",
            description="Create a new document in Outline. Returns the created document's ID and URL.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Document title"
                    },
                    "text": {
                        "type": "string",
                        "description": "Document content (markdown)"
                    },
                    "collection_id": {
                        "type": "string",
                        "description": "Collection ID (optional - creates in default collection if not specified)"
                    },
                    "publish": {
                        "type": "boolean",
                        "description": "Whether to publish immediately (default: true)",
                        "default": True
                    }
                },
                "required": ["title", "text"]
            }
        ),
        Tool(
            name="update_document",
            description="Update an existing document. Returns success status and updated document info.",
            inputSchema={
                "type": "object",
                "properties": {
                    "document_id": {
                        "type": "string",
                        "description": "Document ID to update"
                    },
                    "title": {
                        "type": "string",
                        "description": "New title (optional)"
                    },
                    "text": {
                        "type": "string",
                        "description": "New content (markdown, optional)"
                    },
                    "publish": {
                        "type": "boolean",
                        "description": "Whether to publish (optional)"
                    }
                },
                "required": ["document_id"]
            }
        ),
        Tool(
            name="list_collections",
            description="List all available collections in Outline. Returns collection names, IDs, and descriptions.",
            inputSchema={
                "type": "object",
                "properties": {}
            }
        ),
        Tool(
            name="list_documents_in_collection",
            description="List all documents in a specific collection. Returns document titles, IDs, and URLs.",
            inputSchema={
                "type": "object",
                "properties": {
                    "collection_id": {
                        "type": "string",
                        "description": "Collection ID"
                    }
                },
                "required": ["collection_id"]
            }
        )
    ]


@app.call_tool()
@handle_errors
async def call_tool(name: str, arguments: Any) -> list[TextContent]:
    """Handle tool calls"""

    if name == "search_docs":
        query = arguments.get("query", "")
        limit = arguments.get("limit", 10)

        result = outline_client.post("/documents.search", {
            "query": query,
            "limit": limit
        })

        documents = result.get("documents", [])
        formatted_results = []
        for doc in documents:
            formatted_results.append({
                "id": doc.get("id"),
                "title": doc.get("title"),
                "url": doc.get("url"),
                "snippet": doc.get("text", "")[:200] + "..." if len(doc.get("text", "")) > 200 else doc.get("text", ""),
                "updated_at": doc.get("updatedAt")
            })

        return [TextContent(
            type="text",
            text=json.dumps({
                "query": query,
                "total_results": len(formatted_results),
                "documents": formatted_results
            }, indent=2)
        )]

    elif name == "get_document":
        document_id = arguments.get("document_id")

        result = outline_client.post("/documents.info", {
            "id": document_id
        })

        document = result.get("document", {})
        return [TextContent(
            type="text",
            text=json.dumps({
                "id": document.get("id"),
                "title": document.get("title"),
                "text": document.get("text"),
                "url": document.get("url"),
                "created_at": document.get("createdAt"),
                "updated_at": document.get("updatedAt"),
                "created_by": document.get("createdBy", {}).get("name"),
                "collection_id": document.get("collectionId")
            }, indent=2)
        )]

    elif name == "create_document":
        title = arguments.get("title")
        text = arguments.get("text")
        collection_id = arguments.get("collection_id")
        publish = arguments.get("publish", True)

        data = {
            "title": title,
            "text": text,
            "publish": publish
        }
        if collection_id:
            data["collectionId"] = collection_id

        result = outline_client.post("/documents.create", data)

        document = result.get("document", {})
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "document_id": document.get("id"),
                "url": document.get("url"),
                "title": document.get("title")
            }, indent=2)
        )]

    elif name == "update_document":
        document_id = arguments.get("document_id")

        data = {"id": document_id}
        if "title" in arguments:
            data["title"] = arguments["title"]
        if "text" in arguments:
            data["text"] = arguments["text"]
        if "publish" in arguments:
            data["publish"] = arguments["publish"]

        result = outline_client.post("/documents.update", data)

        document = result.get("document", {})
        return [TextContent(
            type="text",
            text=json.dumps({
                "success": True,
                "document_id": document.get("id"),
                "url": document.get("url"),
                "updated_at": document.get("updatedAt")
            }, indent=2)
        )]

    elif name == "list_collections":
        result = outline_client.post("/collections.list", {})

        collections = result.get("collections", [])
        formatted_collections = []
        for col in collections:
            formatted_collections.append({
                "id": col.get("id"),
                "name": col.get("name"),
                "description": col.get("description"),
                "url": col.get("url"),
                "document_count": col.get("documentCount", 0)
            })

        return [TextContent(
            type="text",
            text=json.dumps({
                "total_collections": len(formatted_collections),
                "collections": formatted_collections
            }, indent=2)
        )]

    elif name == "list_documents_in_collection":
        collection_id = arguments.get("collection_id")

        result = outline_client.post("/documents.list", {
            "collectionId": collection_id
        })

        documents = result.get("documents", [])
        formatted_docs = []
        for doc in documents:
            formatted_docs.append({
                "id": doc.get("id"),
                "title": doc.get("title"),
                "url": doc.get("url"),
                "updated_at": doc.get("updatedAt")
            })

        return [TextContent(
            type="text",
            text=json.dumps({
                "collection_id": collection_id,
                "total_documents": len(formatted_docs),
                "documents": formatted_docs
            }, indent=2)
        )]

    else:
        raise ValueError(f"Unknown tool: {name}")


def main():
    """Main entry point"""
    import asyncio
    from mcp.server.stdio import stdio_server

    async def run():
        async with stdio_server() as (read_stream, write_stream):
            await app.run(
                read_stream,
                write_stream,
                app.create_initialization_options()
            )

    asyncio.run(run())


if __name__ == "__main__":
    main()
