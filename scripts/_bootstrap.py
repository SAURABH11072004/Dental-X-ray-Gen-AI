"""Make scripts runnable from a fresh checkout without installing the package."""
import sys
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
ROOT = SRC.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
