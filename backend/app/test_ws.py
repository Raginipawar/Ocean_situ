import asyncio
import json

async def test_ws():
    import websockets

    uri = "ws://localhost:8000/ws/alerts"
    msgs = []

    async with websockets.connect(uri) as ws:
        # Collect up to 2 messages (ack + possible flushed alerts)
        for _ in range(2):
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=8.0)
                msg = json.loads(raw)
                msgs.append(msg)
                idx = len(msgs) - 1
                mtype = msg["type"]
                if mtype == "connection_ack":
                    text = msg["payload"]["message"]
                    print(f"  msg[{idx}] type=connection_ack -> {text}")
                elif mtype == "alert":
                    n = len(msg["payload"])
                    print(f"  msg[{idx}] type=alert -> {n} alert(s)")
                    for a in msg["payload"]:
                        sev = a["severity"]
                        text = a["message"]
                        print(f"    [{sev}] {text}")
                else:
                    print(f"  msg[{idx}] type={mtype}")
            except asyncio.TimeoutError:
                print("  (timeout — no more messages)")
                break

        # Test: send a filter command
        cmd = json.dumps({"action": "filter", "min_severity": "critical"})
        await ws.send(cmd)
        print("  Filter command sent OK")

    ack_ok = any(m["type"] == "connection_ack" for m in msgs)
    print()
    print("WEBSOCKET TEST PASSED" if ack_ok else "FAIL: no connection_ack received")

asyncio.run(test_ws())
