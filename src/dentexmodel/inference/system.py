"""Hardware / dependency introspection without importing heavy libraries unless installed."""
from __future__ import annotations

import importlib.util
import platform
import shutil
import subprocess
import sys


def module_version(name: str) -> str | None:
    if importlib.util.find_spec(name) is None:
        return None
    try:
        mod = __import__(name)
        return getattr(mod, "__version__", "installed")
    except Exception:  # noqa: BLE001
        return "installed (import failed)"


def gpu_info() -> dict:
    """CUDA status. Uses PyTorch if installed, otherwise ``nvidia-smi``. Nothing is hard-coded."""
    info = {"cuda_available": False, "torch_installed": importlib.util.find_spec("torch") is not None,
            "gpu_name": None, "memory_total_mb": None, "memory_used_mb": None, "driver": None, "source": None}
    if info["torch_installed"]:
        try:
            import torch  # type: ignore
            info["torch_version"] = torch.__version__
            if torch.cuda.is_available():
                info.update(cuda_available=True, gpu_name=torch.cuda.get_device_name(0), source="torch")
                free, total = torch.cuda.mem_get_info(0)
                info.update(memory_total_mb=round(total / 2**20), memory_used_mb=round((total - free) / 2**20))
                return info
        except Exception as exc:  # noqa: BLE001
            info["error"] = str(exc)
    exe = shutil.which("nvidia-smi")
    if exe:
        try:
            out = subprocess.run([exe, "--query-gpu=name,memory.total,memory.used,driver_version", "--format=csv,noheader,nounits"],
                                 capture_output=True, text=True, timeout=5).stdout.strip().splitlines()
            if out:
                name, tot, used, drv = [x.strip() for x in out[0].split(",")]
                info.update(gpu_name=name, memory_total_mb=int(tot), memory_used_mb=int(used), driver=drv, source="nvidia-smi",
                            cuda_available=info.get("cuda_available", False))
        except Exception as exc:  # noqa: BLE001
            info["error"] = str(exc)
    if not info["cuda_available"]:
        info["note"] = ("CUDA not available to PyTorch." if info["torch_installed"] else "PyTorch is not installed; CPU-only features only.")
    return info


def environment_report() -> dict:
    mods = {m: module_version(m) for m in ("numpy", "PIL", "cv2", "yaml", "dotenv", "torch", "torchvision", "fastapi", "uvicorn",
                                           "pydantic", "sklearn", "skimage", "albumentations", "pytest")}
    return {"python": sys.version.split()[0], "platform": platform.platform(), "packages": mods, "gpu": gpu_info()}
