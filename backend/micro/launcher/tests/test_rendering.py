from datetime import timedelta
from pathlib import Path

import pytest
from jinja2 import Environment, PackageLoader
from sfapi_client.compute import Machine

from interactem.launcher.config import cfg
from interactem.launcher.constants import LAUNCH_AGENT_TEMPLATE
from interactem.launcher.models import JobSubmitRequest

HERE = Path(__file__).parent


@pytest.fixture
def expected_script() -> str:
    with open(HERE / "expected_script.sh") as f:
        return f.read()


@pytest.mark.asyncio
async def test_submit_rendering(expected_script: str):
    job_req = JobSubmitRequest(
        machine=Machine.perlmutter,
        account="test_account",
        qos="normal",
        constraint="gpu",
        walltime=timedelta(hours=1, minutes=30),
        reservation=None,
        num_nodes=2,
    )

    jinja_env = Environment(
        loader=PackageLoader("interactem.launcher"), enable_async=True
    )
    template = jinja_env.get_template(LAUNCH_AGENT_TEMPLATE)

    script = await template.render_async(
        job=job_req.model_dump(), settings=cfg.model_dump()
    )

    assert script == expected_script
