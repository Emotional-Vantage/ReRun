import asyncio
import json
from collections import defaultdict
from typing import Dict, Set

from agent.events import subscribe, unsubscribe, Event
from backend.app.db import get_events_since

class StreamManager:
    # How long to wait for an event before emitting a keep-alive frame. Bounding this is what
    # lets the response complete, so a server shutdown or reload is never blocked by an idle
    # dashboard tab.
    HEARTBEAT_SECONDS = 15.0

    def __init__(self):
        # project_id -> set of (queue, loop)
        self.listeners: Dict[str, Set[tuple]] = defaultdict(set)
        subscribe(self.handle_new_event)

    def handle_new_event(self, event: Event):
        if event.project_id in self.listeners:
            for queue, loop in list(self.listeners[event.project_id]):
                try:
                    loop.call_soon_threadsafe(queue.put_nowait, event)
                except Exception:
                    pass

    async def event_generator(self, project_id: str, last_event_id: int, request=None):
        # 1. Yield caught-up events from DB
        db_events = get_events_since("data/rerun.db", project_id, last_event_id)
        for ev_dict in db_events:
            last_event_id = ev_dict["id"]
            yield f"id: {last_event_id}\nevent: message\ndata: {json.dumps(ev_dict)}\n\n"

        # 2. Live event stream with bounded wait and heartbeat
        queue = asyncio.Queue()
        loop = asyncio.get_event_loop()
        listener_tuple = (queue, loop)
        self.listeners[project_id].add(listener_tuple)

        try:
            while True:
                if request is not None:
                    try:
                        if await request.is_disconnected():
                            break
                    except Exception:
                        pass

                try:
                    ev: Event = await asyncio.wait_for(
                        queue.get(), timeout=self.HEARTBEAT_SECONDS
                    )
                except asyncio.TimeoutError:
                    yield ": heartbeat\n\n"
                    continue

                if ev.id > last_event_id:
                    ev_dict = ev.model_dump()
                    yield f"id: {ev.id}\nevent: message\ndata: {json.dumps(ev_dict)}\n\n"
                    last_event_id = ev.id
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            if listener_tuple in self.listeners[project_id]:
                self.listeners[project_id].remove(listener_tuple)

stream_manager = StreamManager()
