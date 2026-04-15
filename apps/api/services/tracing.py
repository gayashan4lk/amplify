"""Best-effort LangSmith trace id lookup (T085).

Returns the current run's trace id when LangSmith tracing is active, else
None. Never raises — tracing is observability, it must not break callers.
"""

from __future__ import annotations

import contextlib


def get_current_trace_id() -> str | None:
    with contextlib.suppress(Exception):
        from langsmith.run_helpers import get_current_run_tree  # type: ignore

        run = get_current_run_tree()
        if run is None:
            return None
        trace_id = getattr(run, "trace_id", None) or getattr(run, "id", None)
        return str(trace_id) if trace_id else None
    return None
