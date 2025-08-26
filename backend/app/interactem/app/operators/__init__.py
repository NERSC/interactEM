import json
from typing import Any, Coroutine
import asyncio
from pathlib import Path

import httpx
from jsonpath_ng import parse

from interactem.app.core.config import settings
from interactem.app.operators.registry import ContainerRegistry
from interactem.core.models.spec import OperatorSpec, OperatorSpecID
from interactem.core.logger import get_logger

OPERATOR_SPEC_KEY = "interactem.operator.spec"
OPERATOR_JSON_FILENAME = "operator.json"
logger = get_logger()


async def _labels(
    registry: ContainerRegistry, image: str, tag: str
) -> dict[str, Any] | None:
    manifest = await registry.manifest(image, tag)
    path = parse("$.config.digest")
    matches = path.find(manifest)
    if not matches:
        logger.warning(
            f"Digest not found in manifest for image '{image}:{tag}'. Skipping."
        )
        return None

    digest = matches[0].value
    blob = await registry.blob(image, digest)

    path = parse("$.config.Labels")
    matches = path.find(blob)
    if not matches:
        logger.warning(
            f"Labels not found in blob for image '{image}:{tag}' (digest: {digest}). Skipping."
        )
        return None

    labels = matches[0].value

    return labels


async def _operator(
    registry: ContainerRegistry, image: str, tag: str
) -> dict[str, Any] | None:
    try:
        labels = await _labels(registry, image, tag)
        if labels is None:
            return None
    except httpx.HTTPStatusError as e:
        logger.warning(f"Failed to fetch labels for {image}:{tag}: {e}")
        return None
    if OPERATOR_SPEC_KEY in labels:
        try:
            return json.loads(labels[OPERATOR_SPEC_KEY])
        except json.JSONDecodeError:
            logger.warning(f"Failed to decode operator spec JSON for {image}:{tag}")
            return None

    return None


async def _fetch_operator(
    registry: ContainerRegistry, image: str
) -> OperatorSpec | None:
    tags = await registry.tags(image)
    # For now only include images with a latest tag
    if "latest" in tags:
        operator = await _operator(registry, image, "latest")
        if operator:
            return OperatorSpec(**operator)

    return None


async def fetch_operators() -> list[OperatorSpec]:
    # Load local operators from mounted directory
    local_ops: list[OperatorSpec] = []
    local_dir = Path(settings.LOCAL_OPERATORS_DIR)
    if local_dir.exists() and local_dir.is_dir():
        for sub in local_dir.iterdir():
            if not sub.is_dir():
                continue
            op_file = sub / OPERATOR_JSON_FILENAME
            if not op_file.exists():
                continue
            try:
                with op_file.open("r", encoding="utf-8") as f:
                    op = json.load(f)
                    local_ops.append(OperatorSpec(**op))
            except Exception:
                logger.warning(f"Failed to load local operator file: {op_file}")

    logger.info("Loaded local operators: %s", [op.label for op in local_ops])

    # Fetch operators from the container registry
    async with ContainerRegistry(
        str(settings.CONTAINER_REGISTRY_URL),
        settings.GITHUB_USERNAME,
        settings.GITHUB_TOKEN,
    ) as registry:
        images = await registry.images(settings.CONTAINER_REGISTRY_NAMESPACE)
        prefix = f"{settings.CONTAINER_REGISTRY_NAMESPACE}/{settings.OPERATOR_CONTAINER_PREFIX}"
        images = [image for image in images if image.startswith(prefix)]

        fetch_operator_tasks: list[Coroutine[Any, Any, OperatorSpec | None]] = []
        for image in images:
            fetch_operator_tasks.append(_fetch_operator(registry, image))

        registry_ops = await asyncio.gather(*fetch_operator_tasks)
        registry_ops = [op for op in registry_ops if op]

    merged: dict[OperatorSpecID, OperatorSpec] = {op.id: op for op in registry_ops}
    merged.update({op.id: op for op in local_ops})

    return [op for op in merged.values()]
