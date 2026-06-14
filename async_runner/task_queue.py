"""
async_runner/task_queue.py
---------------------------
Thread pool for running pipeline jobs in the background.
Streamlit reruns poll for completion via job_id stored in session state.
"""
from __future__ import annotations
import uuid
from concurrent.futures import ThreadPoolExecutor, Future
from typing import Callable, Any

_POOL = ThreadPoolExecutor(max_workers=4, thread_name_prefix="trading-worker")
_JOBS: dict[str, Future] = {}   # job_id → Future


def submit(fn: Callable, *args, **kwargs) -> str:
    """Submit a function to the thread pool. Returns a job_id string."""
    job_id = str(uuid.uuid4())
    future = _POOL.submit(fn, *args, **kwargs)
    _JOBS[job_id] = future
    return job_id


def get_status(job_id: str) -> str:
    """Returns 'pending' | 'running' | 'done' | 'error' | 'not_found'."""
    future = _JOBS.get(job_id)
    if future is None:
        return "not_found"
    if future.running():
        return "running"
    if future.done():
        exc = future.exception()
        return "error" if exc else "done"
    return "pending"


def get_result(job_id: str) -> tuple[Any, Exception | None]:
    """Returns (result, exception). Call only when status is 'done' or 'error'."""
    future = _JOBS.get(job_id)
    if future is None:
        return None, RuntimeError("Job not found")
    exc = future.exception()
    if exc:
        return None, exc
    return future.result(), None


def cleanup(job_id: str):
    """Remove a completed job from the registry."""
    _JOBS.pop(job_id, None)
