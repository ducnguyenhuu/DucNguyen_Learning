"""Quick test: send a chat message via WebSocket streaming and print events."""
import asyncio
import json
import httpx
import websockets

BASE = "http://127.0.0.1:8000/api/v1"
WS_BASE = "ws://127.0.0.1:8000/api/v1"


async def main() -> None:
    # Create a conversation via REST
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE}/conversations", json={})
        conv_id = resp.json()["id"]
        print(f"Conversation: {conv_id}")

    # Connect via WebSocket and send the question
    uri = f"{WS_BASE}/conversations/{conv_id}/stream"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"type": "question", "content": "Who won the last FIFA World Cup?"}))
        print("Sent question, waiting for events...\n")

        async for raw in ws:
            event = json.loads(raw)
            etype = event.get("type", "unknown")
            if etype == "token":
                print(event["content"], end="", flush=True)
            elif etype == "complete":
                print(f"\n\n[complete] message_id={event['message_id']}")
                break
            elif etype == "error":
                print(f"\n[error] {event['message']}")
                break
            elif etype == "sources_found":
                srcs = [s["file_name"] for s in event.get("sources", [])]
                print(f"[sources] {', '.join(srcs)}")
            elif etype == "user_message_saved":
                print(f"[user_saved] {event['message_id']}")
            else:
                print(f"[{etype}] {event}")


if __name__ == "__main__":
    asyncio.run(main())
