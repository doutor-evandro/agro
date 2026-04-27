from __future__ import annotations

class TkScheduler:
    def __init__(self, tk_root, min_sec: int = 30):
        self.root = tk_root
        self.min_sec = min_sec
        self._job = None
        self._running = False

    def start(self, interval_sec: int, callback):
        self.stop()
        self._running = True
        sec = max(self.min_sec, int(interval_sec))
        self._schedule(sec, callback)

    def _schedule(self, sec: int, callback):
        if not self._running:
            return
        self._job = self.root.after(sec * 1000, lambda: self._tick(sec, callback))

    def _tick(self, sec: int, callback):
        if not self._running:
            return
        callback()
        self._schedule(sec, callback)

    def stop(self):
        self._running = False
        if self._job is not None:
            try:
                self.root.after_cancel(self._job)
            except Exception:
                pass
        self._job = None

    @property
    def running(self) -> bool:
        return self._running
