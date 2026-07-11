"""Local-first reference intelligence engine."""

from .models import ReferenceProject
from .pipeline import ReferencePipeline

__all__ = ["ReferencePipeline", "ReferenceProject"]
__version__ = "0.1.0"
