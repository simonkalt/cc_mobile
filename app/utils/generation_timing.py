"""
Lightweight per-request timing tracker for letter generation.
Set ENABLE_GENERATION_TIMING_CHART=false to disable all logs.
"""
from __future__ import annotations

import time
from typing import List, Optional, Tuple


class GenerationTiming:
    def __init__(
        self,
        *,
        enabled: bool,
        flow_name: str,
        client_start_ms: Optional[int] = None,
    ) -> None:
        self.enabled = enabled
        self.flow_name = flow_name
        self._events: List[Tuple[str, float]] = []
        self._start = time.perf_counter()
        self._client_start_ms = client_start_ms

    def checkpoint(self, label: str) -> None:
        if not self.enabled:
            return
        self._events.append((label, time.perf_counter()))

    def _segments(self) -> List[Tuple[str, float]]:
        if not self.enabled or len(self._events) < 2:
            return []
        out: List[Tuple[str, float]] = []
        for i in range(1, len(self._events)):
            prev_label, prev_t = self._events[i - 1]
            curr_label, curr_t = self._events[i]
            out.append((f"{prev_label} -> {curr_label}", max(0.0, curr_t - prev_t)))
        return out

    def chart(self) -> str:
        segments = self._segments()
        if not segments:
            return f"{self.flow_name}: timing disabled or insufficient checkpoints"

        max_secs = max(sec for _, sec in segments) or 1e-9
        width = 24
        lines = [f"{self.flow_name} timing chart (seconds):"]
        for label, sec in segments:
            bar_len = max(1, int((sec / max_secs) * width))
            bar = "#" * bar_len
            lines.append(f"{sec:7.3f}s | {bar:<24} | {label}")

        backend_total = max(0.0, (self._events[-1][1] - self._start))
        lines.append(f"backend_total: {backend_total:.3f}s")

        if self._client_start_ms:
            now_ms = int(time.time() * 1000)
            total_from_click = max(0.0, (now_ms - int(self._client_start_ms)) / 1000.0)
            lines.append(f"frontend_click_to_response: {total_from_click:.3f}s")

        return "\n".join(lines)

