"""
Runner for Mini-Devin Chainlit Console.

Bypasses nest_asyncio compatibility issues on Python 3.14 while preserving
full Chainlit server lifecycle, WebSockets, callbacks, and LangGraph integration.
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

import uvicorn

# Setup paths
base_dir = Path(__file__).resolve().parent
os.environ.setdefault("CHAINLIT_APP_ROOT", str(base_dir))
os.environ.setdefault("MINI_DEVIN_MIN_CONFIDENCE", "0.40")
backend_dir = str(base_dir.parent / "backend")
console_dir = str(base_dir)

while backend_dir in sys.path:
    sys.path.remove(backend_dir)
while console_dir in sys.path:
    sys.path.remove(console_dir)
sys.path.insert(0, backend_dir)

if "app" in sys.modules and not hasattr(sys.modules["app"], "__path__"):
    del sys.modules["app"]

from chainlit.config import config, load_module
from chainlit.markdown import init_markdown
from chainlit.auth import ensure_jwt_secret
from chainlit.cache import init_lc_cache

target = str(base_dir / "app.py")
config.run.host = os.environ.get("CHAINLIT_HOST", "127.0.0.1")
config.run.port = int(os.environ.get("CHAINLIT_PORT", "8000"))
config.run.module_name = target

load_module(target)
while console_dir in sys.path:
    sys.path.remove(console_dir)
ensure_jwt_secret()
init_markdown(config.root)
init_lc_cache()

from chainlit.server import app

async def start():
    uvicorn_config = uvicorn.Config(
        app,
        host=config.run.host,
        port=config.run.port,
        log_level="info",
        ws="auto",
    )
    server = uvicorn.Server(uvicorn_config)
    await server.serve()

if __name__ == "__main__":
    print(f"Starting Mini-Devin Chainlit Console on http://{config.run.host}:{config.run.port}...")
    asyncio.run(start())
