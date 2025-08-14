
import asyncio
import aiohttp
import time
import uuid
import sys
import argparse
from collections import defaultdict

"""
sse fanout load test (htmx-compatible)

- opens n concurrent sse connections to /event/{code}/stream
- sends k*m test messages (from k "senders")
- verifies how many clients received all test messages for this run
- prints basic latency stats

usage:
  python sse_load_test.py --base-url https://your.app --code abc123 \
      --clients 180 --senders 5 --messages-per-sender 2 \
      --post-path /event/{code}/send  --concurrency 5

    python sse_load_test.py \
    --base-url https://eventsky.onrender.com \
    --code 123 \
    --clients 180 \
    --senders 5 \
    --messages-per-sender 2 \
    --stream-path /event/{code}/stream \
    --post-path /event/{code}/message \
    --timeout 40

notes:
- this assumes you can post a message to an endpoint (given by --post-path)
  which will cause your server to broadcast over sse.
- the post body is json: {"text": "...", "sender_name": "loadtester"}
  adjust with --post-json if your api differs.
- the sse messages can be html or json; we only look for a run marker string.
"""

def default_post_json(run_id: str, msg_id: int):
    # customize if your api needs different fields
    return {
        "text": f"[lt-{run_id}] message #{msg_id}",
        "sender_name": "loadtester"
    }

def parse_args():
    p = argparse.argumentparser()
    p.add_argument("--base-url", required=true, help="base url, e.g. https://your.app")
    p.add_argument("--code", required=true, help="event code used in your routes")
    p.add_argument("--clients", type=int, default=50, help="number of concurrent sse clients")
    p.add_argument("--senders", type=int, default=3, help="number of concurrent senders")
    p.add_argument("--messages-per-sender", type=int, default=2, help="messages per sender")
    p.add_argument("--stream-path", default="/event/{code}/stream", help="sse stream path")
    p.add_argument("--post-path", default="/event/{code}/message", help="post path to create/send a message")
    p.add_argument("--timeout", type=float, default=30.0, help="overall test timeout (s)")
    p.add_argument("--concurrency", type=int, default=5, help="http connection pool size")
    p.add_argument("--post-json", default=none,
                   help="python expression evaluated to build the post json. "
                        "it will be eval'd with variables (run_id, msg_id). "
                        "default uses {'text', 'sender_name'}.")
    return p.parse_args()

async def open_sse(session: aiohttp.clientsession, url: str, client_id: int, run_marker: str, inbox: set):
    """
    very small sse client: reads the stream, collects messages containing run_marker.
    """
    try:
        async with session.get(url, timeout=none) as resp:
            if resp.status != 200:
                print(f"[client {client_id}] http {resp.status} opening sse")
                return
            buf = ""
            async for chunk, _ in resp.content.iter_chunks():
                if chunk is none:
                    await asyncio.sleep(0)
                    continue
                buf += chunk.decode("utf-8", errors="ignore")
                # sse frames separated by double newline
                while "\n\n" in buf:
                    frame, buf = buf.split("\n\n", 1)
                    # we only care about 'data: ...' lines, but accept any; look for the marker
                    data_lines = [line[5:].strip() for line in frame.splitlines() if line.startswith("data:")]
                    if not data_lines:
                        continue
                    data = "\n".join(data_lines)
                    if run_marker in data:
                        # extract msg_id if present like: [lt-<run>] message #<id>
                        # fallback: just record the whole line
                        inbox.add(data)
    except asyncio.cancellederror:
        pass
    except exception as e:
        print(f"[client {client_id}] sse error: {e}")

async def sender(session: aiohttp.clientsession, url: str, payload_builder, start_id: int, count: int, delay: float=0.2, record=none):
    """
    sends `count` messages, spacing them by `delay` seconds.
    """
    for i in range(count):
        msg_id = start_id + i
        payload = payload_builder(msg_id)
        t0 = time.perf_counter()
        async with session.post(url, json=payload) as resp:
            text = await resp.text()
            if record is not none:
                record.append((msg_id, resp.status, time.perf_counter() - t0))
            if resp.status >= 300:
                print(f"[sender] post {url} -> {resp.status} {text[:120]}")
        await asyncio.sleep(delay)

async def main():
    args = parse_args()
    run_id = uuid.uuid4().hex[:8]
    run_marker = f"[lt-{run_id}]"
    total_msgs = args.senders * args.messages_per_sender

    stream_url = args.base_url.rstrip("/") + args.stream_path.format(code=args.code)
    post_url   = args.base_url.rstrip("/") + args.post_path.format(code=args.code)

    # build post payload function
    if args.post_json:
        # unsafe eval by design for power-users; keep out of prod code
        def payload_builder(msg_id: int):
            return eval(args.post_json, {"run_id": run_id, "msg_id": msg_id})
    else:
        def payload_builder(msg_id: int):
            return default_post_json(run_id, msg_id)

    timeout = aiohttp.clienttimeout(total=none, sock_read=none, sock_connect=30)
    conn = aiohttp.tcpconnector(limit=args.concurrency)
    async with aiohttp.clientsession(timeout=timeout, connector=conn) as session:
        # start sse clients
        client_inboxes = [set() for _ in range(args.clients)]
        client_tasks = [
            asyncio.create_task(open_sse(session, stream_url, i, run_marker, client_inboxes[i]))
            for i in range(args.clients)
        ]
        # let clients connect
        await asyncio.sleep(1.5)

        # send messages from k senders
        per_sender = args.messages_per_sender
        send_records = []
        sender_tasks = []
        next_id = 1
        for k in range(args.senders):
            sender_tasks.append(asyncio.create_task(sender(
                session, post_url,
                payload_builder=lambda mid, _k=k: default_post_json(run_id, mid) if args.post_json is none
                else eval(args.post_json, {"run_id": run_id, "msg_id": mid}),
                start_id=next_id,
                count=per_sender,
                delay=0.15,
                record=send_records
            )))
            next_id += per_sender

        # wait for senders to finish
        await asyncio.gather(*sender_tasks)

        # wait up to timeout for all clients to receive all messages
        deadline = time.time() + args.timeout
        expected_strings = {f"{run_marker} message #"+str(i) for i in range(1, total_msgs+1)}
        # loop until all got everything or timeout
        while time.time() < deadline:
            all_ok = all(expected_strings.issubset(inbox_texts(client_inboxes[i])) for i in range(args.clients))
            if all_ok:
                break
            await asyncio.sleep(0.5)

        # cancel clients (stop the open streams)
        for t in client_tasks:
            t.cancel()
        await asyncio.gather(*client_tasks, return_exceptions=true)

        # report
        received_counts = [len(expected_strings.intersection(inbox_texts(client_inboxes[i]))) for i in range(args.clients)]
        full_receivers = sum(1 for c in received_counts if c == total_msgs)
        print("\n=== sse fanout report ===")
        print(f"clients: {args.clients}, senders: {args.senders}, total messages: {total_msgs}")
        print(f"clients that received all messages: {full_receivers}/{args.clients}")
        if full_receivers < args.clients:
            missing = [(i, total_msgs - received_counts[i]) for i in range(args.clients) if received_counts[i] < total_msgs]
            print("clients with missing messages (client_id -> missing count):", missing[:20], ("... (truncated)" if len(missing) > 20 else ""))

        if send_records:
            statuses = [s for _, s, _ in send_records]
            rtts = [rt for _, _, rt in send_records]
            ok = sum(1 for s in statuses if s < 300)
            print(f"post success: {ok}/{len(statuses)}, median post rtt: {sorted(rtts)[len(rtts)//2]:.3f}s")

def inbox_texts(inbox_set):
    # normalize to a string set; inbox already stores full 'data' strings
    return set(inbox_set)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except keyboardinterrupt:
        sys.exit(130)
