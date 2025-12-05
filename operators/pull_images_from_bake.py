#!/usr/bin/env python3
"""
Pull operator images to Podman based on Docker Bake configuration.

Features:
- Type hints
- Logging replaces print
- Pydantic models for HCL parsing
- Robust search for TAG and operators group
- Colored output for success/failure
- Optional JSON summary output
- Global concurrency limit for Podman API calls
"""

import asyncio
import json
import logging
import os
import sys
from pathlib import Path

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

try:
    import hcl2
except ImportError:
    sys.exit(
        "Error: python-hcl2 package not found. Install with: pip install python-hcl2"
    )

try:
    from podman.client import PodmanClient
except ImportError:
    sys.exit("Error: podman package not found. Install with: pip install podman")


# ==============================
# Settings
# ==============================
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PODMAN_SERVICE_URI: str | None = None
    BAKE_FILE: Path = Field(default=Path(__file__).parent / "docker-bake.hcl")
    REGISTRY: str = Field(default="localhost:5001/ghcr.io/nersc/interactem")
    VERBOSE: bool = Field(default=False)
    JSON_OUTPUT: bool = Field(default=False)
    CONCURRENCY_LIMIT: int = Field(default=5)


settings = Settings()

log_level = logging.DEBUG if settings.VERBOSE else logging.INFO
logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


# ==============================
# Helpers
# ==============================
def fatal(message: str, code: int = 1) -> None:
    """Log error and exit."""
    logger.error(message)
    sys.exit(code)


def colored_status(success: bool) -> str:
    """Return colored checkmark or cross."""
    return "\033[92m✅\033[0m" if success else "\033[91m❌\033[0m"


# ==============================
# Models for Bake Config
# ==============================
class Variable(BaseModel):
    default: str | None = None


class Target(BaseModel):
    tags: list[str] = Field(default_factory=list)


class DockerBakeModel(BaseModel):
    variable: list[dict[str, Variable]] = Field(default_factory=list)
    group: list[dict[str, dict[str, list[str]]]] = Field(default_factory=list)
    target: list[dict[str, Target]] = Field(default_factory=list)


# ==============================
# Docker Bake Config Parser
# ==============================
class DockerBakeConfig:
    def __init__(self, hcl_file: Path):
        self.hcl_file = hcl_file
        self.config = self._parse_hcl()

    def _parse_hcl(self) -> DockerBakeModel:
        try:
            raw_config = hcl2.api.loads(self.hcl_file.read_text())
            logger.debug(f"Parsed HCL raw config: {raw_config}")
            return DockerBakeModel(**raw_config)
        except Exception as e:
            fatal(f"Failed to parse HCL file {self.hcl_file}: {e}")
            raise

    @property
    def registry(self) -> str:
        return settings.REGISTRY

    @property
    def tag(self) -> str:
        env_tag = os.getenv("TAG")
        if env_tag:
            return env_tag
        for var_dict in self.config.variable:
            if "TAG" in var_dict:
                return var_dict["TAG"].default or "latest"
        return "latest"

    def get_base_targets(self) -> list[str]:
        base_target_names = ["base", "operator", "distiller-streaming"]
        groups: list[str] = []
        for group_dict in self.config.group:
            for target_name in base_target_names:
                if target_name in group_dict:
                    groups.extend(group_dict[target_name].get("targets", []))
        if groups:
            return groups

        defined_targets = {
            name for target_dict in self.config.target for name in target_dict
        }
        return [name for name in base_target_names if name in defined_targets]

    def get_operator_targets(self) -> list[str]:
        for group_dict in self.config.group:
            if "operators" in group_dict:
                return group_dict["operators"].get("targets", [])
        return []

    def get_target_tags(self, target_name: str) -> list[str]:
        for target_dict in self.config.target:
            if target_name in target_dict:
                return self._substitute_variables(target_dict[target_name].tags)
        return []

    def _substitute_variables(self, tags: list[str]) -> list[str]:
        return [
            tag.replace("${REGISTRY}", self.registry).replace("${TAG}", self.tag)
            for tag in tags
        ]


# ==============================
# Image Puller
# ==============================
class ImagePuller:
    def __init__(self, bake_config: DockerBakeConfig, podman_socket: str | None = None):
        self.bake_config = bake_config
        self.podman_socket = podman_socket or settings.PODMAN_SERVICE_URI
        self.semaphore = asyncio.Semaphore(settings.CONCURRENCY_LIMIT)

    async def pull_images_to_podman(
        self, targets: list[str] | None = None
    ) -> dict[str, bool]:
        base_targets = self.bake_config.get_base_targets()
        target_list = targets or self.bake_config.get_operator_targets()
        target_list = list(dict.fromkeys(target_list + base_targets))
        if not target_list:
            fatal("No targets found for pulling images")
        podman_kwargs = {"base_url": self.podman_socket} if self.podman_socket else {}

        try:
            with PodmanClient(**podman_kwargs) as client:
                try:
                    logger.info(
                        f"Connected to Podman {client.version().get('Version', 'unknown')}"
                    )
                except Exception as e:
                    fatal(f"Failed to connect to Podman: {e}")

                logger.info(
                    f"Pulling {len(target_list)} targets (limit={self.semaphore._value})..."
                )
                results_list = await asyncio.gather(
                    *(self._pull_target_images(client, t) for t in target_list),
                    return_exceptions=True,
                )

                return {
                    target: not isinstance(result, Exception) and bool(result)
                    for target, result in zip(target_list, results_list, strict=True)
                }
        except Exception as e:
            fatal(f"Error connecting to Podman: {e}")
            raise

    async def _pull_target_images(self, client: PodmanClient, target: str) -> bool:
        tags = self.bake_config.get_target_tags(target)
        if not tags:
            logger.warning(f"No tags found for target {target}")
            return False
        results = await asyncio.gather(
            *(self._pull_single_image(client, target, tag) for tag in tags)
        )
        return all(results)

    async def _pull_single_image(
        self, client: PodmanClient, target: str, tag: str
    ) -> bool:
        async with self.semaphore:
            try:
                logger.debug(f"Pulling {tag} for target {target}...")
                await asyncio.to_thread(client.images.pull, tag, tls_verify=False)

                # Strip registry prefix from tag for local storage
                # Extract just the registry part (e.g., localhost:5001/ or host.containers.internal:5001/)
                registry_prefix = self.bake_config.registry.split("/")[0]  # Get just "localhost:5001"
                registry_prefix = f"{registry_prefix}/"
                clean_tag = tag.replace(registry_prefix, "")

                if clean_tag != tag:
                    logger.debug(f"Tagging {tag} as {clean_tag}")
                    repository, tag_name = (
                        clean_tag.rsplit(":", 1)
                        if ":" in clean_tag
                        else (clean_tag, "latest")
                    )
                    await asyncio.to_thread(
                        client.images.get(tag).tag, repository, tag_name
                    )
                    await asyncio.to_thread(client.images.remove, tag, force=False)

                logger.debug(f"✅ Pulled {tag} for target {target}")
                return True
            except Exception as e:
                logger.error(f"❌ Failed to pull {tag} for target {target}: {e}")
                return False


def main():
    if not settings.BAKE_FILE.exists():
        fatal(f"Docker bake file not found: {settings.BAKE_FILE}")

    bake_config = DockerBakeConfig(settings.BAKE_FILE)
    logger.info(f"Registry: {bake_config.registry}, Tag: {bake_config.tag}")

    puller = ImagePuller(bake_config, settings.PODMAN_SERVICE_URI)
    results = asyncio.run(puller.pull_images_to_podman())

    successful = sum(results.values())
    total = len(results)

    for target, success in results.items():
        logger.info(f"{colored_status(success)} {target}")

    logger.info(f"Pull results: {successful}/{total} targets successful")

    if settings.JSON_OUTPUT:
        print(json.dumps(results, indent=2))

    if successful < total:
        sys.exit(1)

    logger.info("Image pull process completed successfully!")


if __name__ == "__main__":
    main()
