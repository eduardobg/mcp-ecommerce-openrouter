"""Configuracion centralizada: paths del repo y defaults de OpenRouter/MCP."""

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = REPO_ROOT / "data"
CSV_PATH = DATA_DIR / "ecommerce_orders_dataset.csv"
DB_PATH = Path(os.environ.get("ECOMMERCE_DB_PATH", DATA_DIR / "ecommerce_demo.db"))
MCP_SERVER_SCRIPT = REPO_ROOT / "mcp_server" / "server.py"

MCP_HOST = os.environ.get("MCP_HOST", "127.0.0.1")
MCP_PORT = int(os.environ.get("MCP_PORT", "8000"))
MCP_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = os.environ.get("OPENROUTER_MODEL", "nvidia/nemotron-3-ultra-550b-a55b:free")

OPENROUTER_HEADERS = {
    "HTTP-Referer": "https://github.com/eduardobg/mcp-ecommerce-openrouter",
    "X-OpenRouter-Title": "MCP LangGraph Multiagentes - Streamlit",
}


def get_openrouter_api_key() -> str | None:
    """Busca la API key en variables de entorno o en st.secrets (si existe)."""
    key = os.environ.get("OPENROUTER_API_KEY")
    if key:
        return key
    try:
        import streamlit as st

        return st.secrets.get("OPENROUTER_API_KEY")
    except Exception:
        return None
