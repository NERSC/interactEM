from ..config import cfg
from ..models.pipeline import PodmanMount, PodmanMountType
from . import MOUNT_DIR

CORE_MOUNT = PodmanMount(
    type=PodmanMountType.bind,
    source=str((cfg.CORE_PACKAGE_DIR / "core").resolve()),
    target=f"{MOUNT_DIR}/core",
)

OPERATORS_MOUNT = PodmanMount(
    type=PodmanMountType.bind,
    source=str((cfg.OPERATORS_PACKAGE_DIR / "operators").resolve()),
    target=f"{MOUNT_DIR}/operators",
)
