from rich.console import Console
from rich.progress import (
    Progress,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    TimeRemainingColumn,
    SpinnerColumn,
)
from rich.live import Live
from rich.table import Table
from rich.panel import Panel
from typing import Optional, Dict, Any

class DisplayManager:
    """Manages dynamic CLI output using rich."""

    def __init__(self):
        self.console = Console()
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
        self.tasks: Dict[str, Any] = {}

    def start(self):
        """Start the progress display context."""
        return self.progress

    def add_series_task(self, series_name: str, total: int = 0) -> Any:
        """Add a new progress task for a series."""
        task_id = self.progress.add_task(
            "download", 
            series_name=series_name, 
            status="Waiting...", 
            total=total, 
            start=False
        )
        self.tasks[series_name] = task_id
        return task_id

    def update_status(self, task_id: Any, status: str):
        """Update the status text of a task."""
        self.progress.update(task_id, status=status)

    def update_progress(self, task_id: Any, advance: int = 0, total: Optional[int] = None, status: Optional[str] = None):
        """Update progress bar and optionally status."""
        kwargs = {"advance": advance}
        if total is not None:
            kwargs["total"] = total
        if status is not None:
            kwargs["status"] = status
            
        self.progress.update(task_id, **kwargs)
        
    def start_task(self, task_id: Any):
        """Start the task (timer)."""
        self.progress.start_task(task_id)

    def log(self, message: str, style: str = "info"):
        """Log a message above the progress bars."""
        # rich.progress.Progress.console.print prints above the live display
        self.progress.console.print(message, style=style)
