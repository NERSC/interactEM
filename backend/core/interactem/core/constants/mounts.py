from ..config import cfg
from ..models.containers import PodmanMount, PodmanMountType
from . import PACKAGE_DIR_IN_CONTAINER

CORE_MOUNT = PodmanMount(
    type=PodmanMountType.bind,
    source=str((cfg.CORE_PACKAGE_DIR / "core").resolve()),
    target=f"{PACKAGE_DIR_IN_CONTAINER}/core/interactem/core",
)

OPERATORS_MOUNT = PodmanMount(
    type=PodmanMountType.bind,
    source=str((cfg.OPERATORS_PACKAGE_DIR / "operators").resolve()),
    target=f"{PACKAGE_DIR_IN_CONTAINER}/operators/interactem/operators",
)
