import urllib.parse
from typing import Any

from httpx import AsyncClient, Limits, Timeout
from jsonpath_ng import parse

GITHUB_API_URL = "https://api.github.com"
MANIFEST_MIME_TYPE = "application/vnd.oci.image.manifest.v1+json"
GITHUB_API_MIME_TYPE = "application/vnd.github.v3+json"
BLOB_MIME_TYPE = "application/vnd.docker.distribution.manifest.v2+json"

MAX_CONNECTIONS = 20
READ_TIMEOUT = 30
CONNECT_TIMEOUT = 10


class ContainerRegistry:
    def __init__(
        self,
        url: str,
        username: str,
        password: str,
    ):
        self._url = url
        self._username = username
        self._password = password
        self._token_ = None

    async def __aenter__(self):
        timeout = Timeout(timeout=READ_TIMEOUT, connect=CONNECT_TIMEOUT)
        limits = Limits(max_connections=MAX_CONNECTIONS)
        self._client = AsyncClient(base_url=self._url, timeout=timeout, limits=limits)

        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self._client.aclose()

    async def _token(self) -> str:
        if self._token_ is None:
            params = {
                "scope": "repository:*:pull",
            }

            r = await self._client.get(
                "token", params=params, auth=(self._username, self._password)
            )
            r.raise_for_status()

            self._token_ = r.json()["token"]

        return self._token_

    async def _headers(self):
        token = await self._token()
        return {"Authorization": f"Bearer {token}"}

    async def _ghcr_images(self, org: str) -> list[str]:
        url = f"{GITHUB_API_URL}/orgs/{org}/packages"
        headers = {
            "Accept": GITHUB_API_MIME_TYPE,
            "Authorization": f"Bearer {self._password}",
        }

        all_packages = []
        page = 1
        per_page = 100

        while True:
            params = {
                "package_type": "container",
                "page": page,
                "per_page": per_page,
            }
            r = await self._client.get(url, headers=headers, params=params)
            r.raise_for_status()

            page_data = r.json()
            if not page_data:
                break

            all_packages.extend(page_data)

            if len(page_data) < per_page:
                break

            page += 1

        path = parse("$[*].name")
        matches = path.find(all_packages)
        if not matches:
            raise Exception("Images not found")

        return [f"{org}/{urllib.parse.quote(match.value)}" for match in matches]

    async def images(self, namespace: str) -> list[str]:
        # Special case for GitHub Container Registry, it currently doesn't support
        # the _catalog endpoint
        if urllib.parse.urlparse(self._url).hostname == "ghcr.io":
            return await self._ghcr_images(namespace)

        headers = await self._headers()
        r = await self._client.get("v2/_catalog", headers=headers)
        r.raise_for_status()

        return [f"{namespace}/{r}" for r in r.json()["repositories"]]

    async def manifest(self, image: str, tag: str) -> dict[str, Any]:
        headers = await self._headers()
        headers["Accept"] = MANIFEST_MIME_TYPE

        r = await self._client.get(f"v2/{image}/manifests/{tag}", headers=headers)
        r.raise_for_status()

        return r.json()

    async def blob(self, image: str, digest: str) -> dict[str, Any]:
        headers = await self._headers()
        headers["Accept"] = BLOB_MIME_TYPE
        r = await self._client.get(
            f"v2/{image}/blobs/{digest}", headers=headers, follow_redirects=True
        )
        r.raise_for_status()

        return r.json()

    async def tags(self, image: str) -> list[str]:
        headers = await self._headers()
        r = await self._client.get(f"v2/{image}/tags/list", headers=headers)
        r.raise_for_status()

        return r.json()["tags"]
