"""
Gestion del servidor MCP: arranque como subproceso multiplataforma y
descubrimiento de tools via MultiServerMCPClient.

Reemplaza los Pasos 6-7 del notebook (que usaban `!fuser -k 8000/tcp`,
especifico de Colab/Linux) por una version que tambien funciona en Windows.
"""

import asyncio
import socket
import subprocess
import sys
import time
from dataclasses import dataclass, field

from langchain_mcp_adapters.client import MultiServerMCPClient

from . import config


def puerto_abierto(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex((host, port)) == 0


@dataclass
class McpRuntime:
    """Handle cacheable (via st.cache_resource) del servidor MCP + sus tools."""

    process: subprocess.Popen | None = None
    tools: list = field(default_factory=list)
    tools_por_nombre: dict = field(default_factory=dict)

    def is_port_open(self) -> bool:
        return puerto_abierto(config.MCP_HOST, config.MCP_PORT)

    def stop(self) -> None:
        if self.process is not None and self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.process.kill()
        self.process = None


def _start_process() -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, str(config.MCP_SERVER_SCRIPT)],
        cwd=str(config.REPO_ROOT),
    )


def _wait_for_port(host: str, port: int, retries: int = 40, delay: float = 0.5) -> bool:
    for _ in range(retries):
        if puerto_abierto(host, port):
            return True
        time.sleep(delay)
    return False


async def _discover_tools_async(url: str) -> list:
    client = MultiServerMCPClient({"ecommerce": {"transport": "http", "url": url}})
    return await client.get_tools()


def ensure_running_and_discover() -> McpRuntime:
    """
    Arranca el servidor MCP si el puerto no responde todavia, y descubre sus
    tools. Si el puerto ya esta abierto (por ejemplo, un proceso de una
    corrida anterior que quedo activo), simplemente se reutiliza en vez de
    lanzar uno nuevo.
    """
    runtime = McpRuntime()

    if not runtime.is_port_open():
        runtime.process = _start_process()
        if not _wait_for_port(config.MCP_HOST, config.MCP_PORT):
            raise RuntimeError(
                "El servidor FastMCP no logro iniciar en "
                f"{config.MCP_HOST}:{config.MCP_PORT}. Revisa que el puerto este libre."
            )

    tools = asyncio.run(_discover_tools_async(config.MCP_URL))
    runtime.tools = tools
    runtime.tools_por_nombre = {tool.name: tool for tool in tools}
    return runtime
