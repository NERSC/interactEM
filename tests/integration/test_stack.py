import os
import subprocess
import time
from urllib.error import URLError
from urllib.request import urlopen

import pytest

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8080")


def _list_running_services() -> set[str]:
    result = subprocess.run(
        ["docker", "compose", "ps", "--services", "--status=running"],
        check=True,
        capture_output=True,
        text=True,
    )
    return {service for service in result.stdout.splitlines() if service}


def _wait_for_backend_docs(path: str = "/api/docs", timeout: float = 180.0) -> str:
    deadline = time.time() + timeout
    url = BACKEND_URL.rstrip("/") + path

    while time.time() < deadline:
        try:
            with urlopen(url, timeout=10) as response:  # nosec B310
                if response.status == 200:
                    return response.read().decode("utf-8", errors="replace")
        except URLError:
            pass
        time.sleep(3)

    raise AssertionError(f"Backend docs did not become available at {url}")


@pytest.mark.integration
def test_core_services_are_running():
    running = _list_running_services()
    expected = {"backend", "db", "nats1"}
    missing = expected - running
    assert not missing, f"Expected services not running: {sorted(missing)}"


@pytest.mark.integration
def test_backend_docs_reachable():
    docs_html = _wait_for_backend_docs()
    assert "swagger-ui" in docs_html.lower(), "API docs did not return swagger UI"
