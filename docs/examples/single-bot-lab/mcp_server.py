"""Local teaching fixture: an MCP call produces evidence independent of the LLM."""

import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

from mcp.server.fastmcp import FastMCP

lab = Path(__file__).resolve().parent
mcp = FastMCP("single-bot-lab")


@mcp.tool()
def lab_probe(nonce: str) -> str:
    """Return a fresh receipt for the supplied experiment nonce."""
    if (lab / "fail.flag").exists():
        raise RuntimeError("LAB_INTENTIONAL_FAILURE: remove fail.flag to recover")
    receipt = {
        "nonce": nonce,
        "receipt": secrets.token_hex(12),
        "utc": datetime.now(timezone.utc).isoformat(),
    }
    with (lab / "calls.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt, ensure_ascii=False) + "\n")
    return json.dumps(receipt, ensure_ascii=False)


if __name__ == "__main__":
    mcp.run(transport="stdio")
