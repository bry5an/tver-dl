import os
import re
import logging
from contextlib import nullcontext
from rich.console import Console
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    SpinnerColumn,
)
from typing import Optional, Dict, Any

_IN_DOCKER = os.path.exists('/.dockerenv')
_MARKUP_RE = re.compile(r'\[/?[^\]]*\]')


def _strip_markup(text: str) -> str:
    return _MARKUP_RE.sub('', text)


class DisplayManager:
    """Manages CLI output — Rich progress bars outside Docker, plain logging inside."""

    def __init__(self):
        self.console = Console()
        self._rich = not _IN_DOCKER
        self._logger = logging.getLogger(__name__)
        self.tasks: Dict[str, Any] = {}

        if self._rich:
            self.progress = Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.fields[series_name]}", justify="right"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("{task.fields[status]}"),
                TimeRemainingColumn(),
                console=self.console,
                expand=True,
            )
        else:
            self.progress = None

    def start(self):
        """Return a context manager for the progress display (no-op inside Docker)."""
        if self._rich:
            return self.progress
        return nullcontext()

    def add_series_task(self, series_name: str, total: int = 0) -> Any:
        """Add a new progress task for a series."""
        if self._rich:
            task_id = self.progress.add_task(
                "download",
                series_name=series_name,
                status="Waiting...",
                total=total,
                start=False,
            )
            self.tasks[series_name] = task_id
            return task_id
        return series_name  # opaque ID for log-only path

    def update_status(self, task_id: Any, status: str):
        """Update the status text of a task."""
        if self._rich:
            self.progress.update(task_id, status=status)
        else:
            self._logger.info("%s: %s", task_id, _strip_markup(status))

    def update_progress(self, task_id: Any, advance: int = 0, total: Optional[int] = None,
                        completed: Optional[float] = None, status: Optional[str] = None):
        """Update progress bar and optionally status."""
        if self._rich:
            kwargs: Dict[str, Any] = {"advance": advance}
            if total is not None:
                kwargs["total"] = total
            if completed is not None:
                kwargs["completed"] = completed
            if status is not None:
                kwargs["status"] = status
            self.progress.update(task_id, **kwargs)
        elif status is not None:
            self._logger.info("%s: %s", task_id, _strip_markup(status))

    def start_task(self, task_id: Any):
        """Start the task timer."""
        if self._rich:
            self.progress.start_task(task_id)

    def log(self, message: str, style: str = "info"):
        """Log a message above the progress bars (or to the logger inside Docker)."""
        if self._rich:
            self.progress.console.print(message, style=style)
        else:
            self._logger.info(_strip_markup(message))
