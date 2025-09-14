import asyncio


class EventBroker:
    def __init__(self):
        self.channels = {}  # {event_code: set of queues}

    async def connect(self, event_code):
        q = asyncio.Queue(maxsize=100)
        self.channels.setdefault(event_code, set()).add(q)
        return q

    async def disconnect(self, event_code, q):
        qs = self.channels.get(event_code)
        if not qs:
            return
        qs.discard(q)
        if not qs:
            self.channels.pop(event_code, None)

    async def publish(self, event_code, html):
        lines = html.splitlines()
        frame = "event: message\n" + "".join(f"data: {ln}\n" for ln in lines) + "\n"

        for q in list(self.channels.get(event_code, [])):
            try:
                q.put_nowait(frame)
            except asyncio.QueueFull:
                try:
                    # Drop oldest item to make room
                    _ = q.get_nowait()
                    q.put_nowait(frame)
                except asyncio.QueueFull:
                    # If it's still full (race condition), just skip
                    pass


broker = EventBroker()
