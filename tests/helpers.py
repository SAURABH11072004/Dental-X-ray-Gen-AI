"""Shared test helpers. Everything generated here is SYNTHETIC TEST DATA (see dentexmodel.data.synthetic)."""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
for p in (ROOT / "src", ROOT):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from PIL import Image  # noqa: E402

from dentexmodel.config import Settings, get_settings  # noqa: E402
from dentexmodel.data.synthetic import make_blob_image  # noqa: E402


def make_settings(tmp: Path) -> Settings:
    """Settings rooted in a temporary project directory that has a copy of ``configs/``."""
    (tmp / "src" / "dentexmodel").mkdir(parents=True, exist_ok=True)
    shutil.copytree(ROOT / "configs", tmp / "configs", dirs_exist_ok=True)
    s = get_settings(tmp, load_env=False)
    s.data_root.mkdir(parents=True, exist_ok=True)
    s.ensure_dirs()
    return s


def write_test_data_images(data_root: Path, n: int = 12, subdir="validation_data/quadrant_enumeration_disease/xrays") -> Path:
    """Unlabeled TEST DATA layout (mirrors the real ``validation_data`` folder)."""
    d = data_root / subdir
    d.mkdir(parents=True, exist_ok=True)
    for i in range(n):
        Image.fromarray((make_blob_image(i) * 255).astype("uint8"), mode="L").save(d / f"val_{i}.png")
    return d


def png_bytes(seed: int = 1, w: int = 512, h: int = 256) -> bytes:
    import io
    buf = io.BytesIO()
    Image.fromarray((make_blob_image(seed, w, h) * 255).astype("uint8"), mode="L").save(buf, "PNG")
    return buf.getvalue()


class TmpCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)   # Windows keeps log files open
        self.tmp = Path(self._tmp.name)
        self.s = make_settings(self.tmp)

    def tearDown(self):
        import logging
        for h in list(logging.getLogger().handlers):       # release log files under the temp dir (Windows locks them)
            if getattr(h, "baseFilename", "").startswith(str(self.tmp)):
                h.close()
                logging.getLogger().removeHandler(h)
        self._tmp.cleanup()
