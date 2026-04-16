"""Racing Hub wrappers."""

from src.bibops.racing.hub.ingest import ingest
from src.bibops.racing.hub.server import app

__all__ = ["app", "ingest"]
