from .core import TVerDownloader
from .cli import main

try:
    from ._version import __version__
except ImportError:
    __version__ = "unknown"

__all__ = ["TVerDownloader", "main", "__version__"]
