"""Racing arena wrappers over existing `src.agents_racing` modules."""

from src.bibops.racing.demo import run_demo
from src.bibops.racing.start_arena import main as start_arena

__all__ = ["run_demo", "start_arena"]
