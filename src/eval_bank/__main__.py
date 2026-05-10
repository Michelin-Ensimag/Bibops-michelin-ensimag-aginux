"""Allow `python -m src.eval_bank ...`."""
import sys

from src.eval_bank.cli import main

if __name__ == "__main__":
    sys.exit(main())
