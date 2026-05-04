"""
webhook_queue.py

Bounded outbound webhook queue.  Callers call enqueue() — non-blocking.
One worker thread per unique destination URL handles rate-limit delay and
HTTP send.  Delay logic lives inside the worker; no lock is held during sleep.

Replaces the sleep-inside-lock pattern in the old send_webhook().
"""

from __future__ import annotations

import json
import queue
import threading
import time
from dataclasses import dataclass, field
from typing import Optional

import requests

# Maximum tasks waiting across ALL URLs combined.
# put_nowait() drops the oldest task when the queue is full.
_MAX_QUEUE = 500

# Per-URL rate-limit: minimum seconds between consecutive sends.
# Overridden per-task by delay_ms.
_DEFAULT_RATE_LIMIT_S = 1.0

# After this many consecutive HTTP errors, the worker backs off for
# _ERROR_BACKOFF_S before trying again.
_MAX_CONSECUTIVE_ERRORS = 3
_ERROR_BACKOFF_S = 10.0

# Maximum retry attempts per task (429 or 5xx).
_MAX_RETRIES = 3


@dataclass
class WebhookTask:
    """Immutable description of one outbound webhook send."""
    url:         str
    embed:       dict
    content:     Optional[str]  = None
    image_bytes: Optional[bytes] = None
    delay_ms:    int            = 0
    retry_count: int            = 0


# ── Per-URL worker state ─────────────────────────────────────────────
# All access to these dicts is protected by _registry_lock.
_registry_lock: threading.Lock  = threading.Lock()
_queues:  dict[str, queue.Queue] = {}
_workers: dict[str, threading.Thread] = {}


def _get_or_create_worker(url: str) -> queue.Queue:
    """Return the queue for url, creating a worker thread if needed."""
    with _registry_lock:
        if url not in _queues:
            q: queue.Queue = queue.Queue(maxsize=_MAX_QUEUE)
            t = threading.Thread(
                target=_worker_loop,
                args=(url, q),
                daemon=True,
                name=f"WebhookWorker-{url[:40]}",
            )
            _queues[url]  = q
            _workers[url] = t
            t.start()
        return _queues[url]


def enqueue(task: WebhookTask) -> bool:
    """
    Non-blocking enqueue.  Returns True if accepted, False if dropped
    (queue full — backpressure).  Never blocks the caller.
    """
    if not task.url:
        return False
    q = _get_or_create_worker(task.url)
    try:
        q.put_nowait(task)
        # Warn at 80% capacity — signals backpressure before tasks are dropped.
        depth = q.qsize()
        if depth > _MAX_QUEUE * 0.8:
            print(f"[WEBHOOK-QUEUE] WARNING: queue for {task.url[:40]!r}"
                  f" at {depth}/{_MAX_QUEUE} ({depth/_MAX_QUEUE*100:.0f}%)")
        return True
    except queue.Full:
        print(f"[WEBHOOK-QUEUE] Queue full for {task.url[:40]!r} — task dropped")
        return False


def queue_depth(url: str) -> int:
    """Return the current queue depth for a URL (0 if no worker exists)."""
    with _registry_lock:
        q = _queues.get(url)
    return q.qsize() if q else 0


def total_queue_depth() -> int:
    """Return the sum of all per-URL queue depths."""
    with _registry_lock:
        qs = list(_queues.values())
    return sum(q.qsize() for q in qs)


# ── Worker loop (runs in its own daemon thread per URL) ───────────────

def _send_one(task: WebhookTask) -> tuple[bool, int]:
    """
    Perform the HTTP POST for one task.
    Returns (success: bool, http_status: int).
    http_status is 0 on network exception.
    """
    payload: dict = {"embeds": [task.embed]}
    if task.content:
        payload["content"] = task.content

    try:
        if task.image_bytes:
            resp = requests.post(
                task.url,
                data={"payload_json": json.dumps(payload)},
                files={"file": ("screenshot.png", task.image_bytes, "image/png")},
                timeout=10,
            )
        else:
            resp = requests.post(task.url, json=payload, timeout=10)

        return resp.status_code in (200, 204), resp.status_code

    except Exception as exc:
        print(f"[WEBHOOK-QUEUE] Network error for {task.url[:40]!r}: {exc}")
        return False, 0


def _worker_loop(url: str, q: queue.Queue) -> None:
    """
    Dedicated send loop for one URL.
    - Dequeues tasks one at a time.
    - Applies delay_ms rate limiting AFTER dequeue, with NO lock held.
    - Re-enqueues on 429 / 5xx up to _MAX_RETRIES.
    - Backs off after _MAX_CONSECUTIVE_ERRORS consecutive failures.
    """
    last_sent_at:      float = 0.0
    consecutive_errors: int  = 0

    while True:
        try:
            task: WebhookTask = q.get(timeout=30)
        except queue.Empty:
            # No tasks for 30 s — keep thread alive, try again.
            continue

        # ── Rate-limit sleep (NO lock held) ──────────────────────────
        if task.delay_ms > 0:
            delay_s  = task.delay_ms / 1000.0
            elapsed  = time.time() - last_sent_at
            wait     = delay_s - elapsed
            if wait > 0:
                time.sleep(wait)   # sleep here, never inside a lock

        # ── Send ─────────────────────────────────────────────────────
        success, status = _send_one(task)
        last_sent_at    = time.time()

        if success:
            consecutive_errors = 0
            q.task_done()
            continue

        # ── Retry logic ───────────────────────────────────────────────
        consecutive_errors += 1

        if status == 429:
            # Discord rate limit — back off 5 s then re-enqueue
            print(f"[WEBHOOK-QUEUE] 429 rate-limited on {url[:40]!r}, backing off 5 s")
            time.sleep(5.0)
            if task.retry_count < _MAX_RETRIES:
                try:
                    q.put_nowait(WebhookTask(
                        url=task.url, embed=task.embed,
                        content=task.content, image_bytes=task.image_bytes,
                        delay_ms=task.delay_ms,
                        retry_count=task.retry_count + 1,
                    ))
                except queue.Full:
                    pass

        elif status >= 500:
            # Server error — re-enqueue once
            if task.retry_count < _MAX_RETRIES:
                try:
                    q.put_nowait(WebhookTask(
                        url=task.url, embed=task.embed,
                        content=task.content, image_bytes=task.image_bytes,
                        delay_ms=task.delay_ms,
                        retry_count=task.retry_count + 1,
                    ))
                except queue.Full:
                    pass

        if consecutive_errors >= _MAX_CONSECUTIVE_ERRORS:
            print(f"[WEBHOOK-QUEUE] {consecutive_errors} consecutive errors on {url[:40]!r}, backing off {_ERROR_BACKOFF_S} s")
            time.sleep(_ERROR_BACKOFF_S)
            consecutive_errors = 0

        q.task_done()