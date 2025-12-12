

import os
import shutil
import subprocess


# GPU utils
# =============================================================================
def detect_gpu_enabled() -> bool:
    visible_devices = (
        os.getenv("CUDA_VISIBLE_DEVICES") or os.getenv("NVIDIA_VISIBLE_DEVICES") or ""
    ).strip()
    if visible_devices and visible_devices.lower() not in {"none", "void", "-1"}:
        return True

    if os.path.isdir("/proc/driver/nvidia/gpus"):
        return True

    for path in ("/dev/nvidiactl", "/dev/nvidia0", "/dev/nvidia-uvm"):
        if os.path.exists(path):
            return True

    nvidia_smi = shutil.which("nvidia-smi")
    if not nvidia_smi:
        return False

    try:
        proc = subprocess.run(
            [nvidia_smi, "-L"],
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=1.5,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False

    return proc.returncode == 0 and bool(proc.stdout.strip())
