import json
from typing import Any
import asyncio

from jsonpath_ng import parse

from interactem.app.core.config import settings
from interactem.app.operators.registry import ContainerRegistry
from interactem.core.models.operators import Operator

OPERATOR_SPEC_KEY = "interactem.operator.spec"


async def _labels(registry: ContainerRegistry, image: str, tag: str) -> dict[str, Any]:
    manifest = await registry.manifest(image, tag)
    path = parse("$.config.digest")
    matches = path.find(manifest)
    if not matches:
        raise Exception("Digest not found")

    digest = matches[0].value
    blob = await registry.blob(image, digest)

    path = parse("$.config.Labels")
    matches = path.find(blob)
    if not matches:
        raise Exception("Labels not found")

    labels = matches[0].value

    return labels


async def _operator(
    registry: ContainerRegistry, image: str, tag: str
) -> dict[str, Any]:
    labels = await _labels(registry, image, tag)
    if OPERATOR_SPEC_KEY in labels:
        return json.loads(labels[OPERATOR_SPEC_KEY])

    return None


async def _fetch_operator(registry: ContainerRegistry, image: str) -> dict[str, Any]:
    tags = await registry.tags(image)
    # For now only include images with a latest tag
    if "latest" in tags:
        operator = await _operator(registry, image, "latest")
        if operator:
            return operator

    return None


async def fetch_operators() -> list[Operator]:
    async with ContainerRegistry(
        str(settings.CONTAINER_REGISTRY_URL),
        settings.GITHUB_USERNAME,
        settings.GITHUB_TOKEN,
    ) as registry:
        images = await registry.images(settings.CONTAINER_REGISTRY_NAMESPACE)
        prefix = f"{settings.CONTAINER_REGISTRY_NAMESPACE}/{settings.OPERATOR_CONTAINER_PREFIX}"
        images = [image for image in images if image.startswith(prefix)]

        fetch_operator_tasks = []
        for image in images:
            fetch_operator_tasks.append(_fetch_operator(registry, image))

        ops = await asyncio.gather(*fetch_operator_tasks)

        return [Operator(**op) for op in ops if op]


async def main():
    operators = await fetch_operators()
    print(operators)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
