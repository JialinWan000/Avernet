"""One observable chat turn against Avernet's Engine adapter protocol v3.

Use a fresh connection document obtained through the local Gateway. This is a
learning client, not a replacement for the frontend or a native OpenClaw client.
"""

import argparse
import json
import platform
import time
import uuid
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--connection", type=Path, required=True)
    parser.add_argument("--session", required=True)
    parser.add_argument("--user", required=True)
    parser.add_argument("--message", required=True)
    parser.add_argument("--timeout", type=float, default=180)
    args = parser.parse_args()
    from websockets.sync.client import connect

    document = json.loads(args.connection.read_text(encoding="utf-8"))
    sockets = document["data"]["sockets"]
    url = next(item["url"] for item in sockets if item["kind"] == "chat")
    # The URL may contain a short-lived credential. Never print it.
    deadline = time.monotonic() + args.timeout
    with connect(
        url, additional_headers={"x-dev-user": args.user},
        open_timeout=15, max_size=8 * 1024 * 1024,
    ) as socket:
        socket.send(json.dumps({
            "type": "req", "id": "lab-connect", "method": "connect",
            "params": {
                "minProtocol": 3, "maxProtocol": 3,
                "client": {"id": "single-bot-lab", "version": "1.0",
                           "platform": platform.system().lower(), "mode": "cli"},
                "user_id": args.user,
            },
        }))
        while True:
            hello = json.loads(socket.recv(timeout=10))
            if hello.get("id") == "lab-connect":
                if not hello.get("ok"):
                    print(json.dumps(hello, ensure_ascii=False))
                    return 1
                print("connect: ok (adapter protocol v3)")
                break

        request_id = "lab-" + uuid.uuid4().hex
        socket.send(json.dumps({
            "type": "req", "id": request_id, "method": "chat.send",
            "params": {"sessionKey": args.session, "message": args.message,
                       "idempotencyKey": request_id},
        }))
        print(f"chat.send: id={request_id}, session={args.session}")
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("No terminal chat event before the deadline")
            event = json.loads(socket.recv(timeout=remaining))
            if event.get("event") == "tick":
                continue
            print(json.dumps(event, ensure_ascii=False), flush=True)
            if event.get("type") == "res" and event.get("id") == request_id:
                if not event.get("ok"):
                    return 1
            payload = event.get("payload") or {}
            if event.get("event") == "chat" and payload.get("sessionKey") == args.session:
                state = payload.get("state")
                if state in {"final", "error", "aborted"}:
                    return 0 if state == "final" else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        # Avoid dumping connection URLs or credentials in transport exceptions.
        print(f"Chat failed ({type(error).__name__}). Check the lab guide and local logs.")
        raise SystemExit(1) from None
