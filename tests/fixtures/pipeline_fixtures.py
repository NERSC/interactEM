
import pytest

from zmglue.fixtures import (
    EDGE_0,
    EDGE_1,
    EDGE_2,
    EDGE_3,
    EDGE_4,
    EDGE_5,
    OPERATOR_0,
    OPERATOR_0_ID,
    OPERATOR_0_OUTPUT_0_ID,
    OPERATOR_0_OUTPUT_1_ID,
    OPERATOR_0_PORT_0,
    OPERATOR_0_PORT_1,
    OPERATOR_1,
    OPERATOR_1_ID,
    OPERATOR_1_INPUT_0_ID,
    OPERATOR_1_PORT_0,
    OPERATOR_2,
    OPERATOR_2_ID,
    OPERATOR_2_INPUT_0_ID,
    OPERATOR_2_PORT_0,
    PIPELINE,
)
from zmglue.models import EdgeJSON, OperatorJSON, PipelineJSON, PortJSON
from zmglue.models.base import OperatorID, PortID


@pytest.fixture(scope="module")
def operator_0_id() -> OperatorID:
    return OPERATOR_0_ID


@pytest.fixture(scope="module")
def operator_1_id() -> OperatorID:
    return OPERATOR_1_ID


@pytest.fixture(scope="module")
def operator_2_id() -> OperatorID:
    return OPERATOR_2_ID


@pytest.fixture(scope="module")
def operator_0_output_0_id() -> PortID:
    return OPERATOR_0_OUTPUT_0_ID


@pytest.fixture(scope="module")
def operator_0_output_1_id() -> PortID:
    return OPERATOR_0_OUTPUT_1_ID


@pytest.fixture(scope="module")
def operator_1_input_0_id() -> PortID:
    return OPERATOR_1_INPUT_0_ID


@pytest.fixture(scope="module")
def operator_2_input_0_id() -> PortID:
    return OPERATOR_2_INPUT_0_ID


@pytest.fixture(scope="module")
def operator_0() -> OperatorJSON:
    return OPERATOR_0


@pytest.fixture(scope="module")
def operator_0_port_0() -> PortJSON:
    return OPERATOR_0_PORT_0


@pytest.fixture(scope="module")
def operator_0_port_1() -> PortJSON:
    return OPERATOR_0_PORT_1


@pytest.fixture(scope="module")
def operator_1() -> OperatorJSON:
    return OPERATOR_1


@pytest.fixture(scope="module")
def operator_1_port_0() -> PortJSON:
    return OPERATOR_1_PORT_0


@pytest.fixture(scope="module")
def operator_2() -> OperatorJSON:
    return OPERATOR_2


@pytest.fixture(scope="module")
def operator_2_port_0() -> PortJSON:
    return OPERATOR_2_PORT_0


@pytest.fixture(scope="module")
def edge_0() -> EdgeJSON:
    return EDGE_0


@pytest.fixture(scope="module")
def edge_1() -> EdgeJSON:
    return EDGE_1


@pytest.fixture(scope="module")
def edge_2() -> EdgeJSON:
    return EDGE_2


@pytest.fixture(scope="module")
def edge_3() -> EdgeJSON:
    return EDGE_3


@pytest.fixture(scope="module")
def edge_4() -> EdgeJSON:
    return EDGE_4


@pytest.fixture(scope="module")
def edge_5() -> EdgeJSON:
    return EDGE_5


@pytest.fixture(scope="module")
def pipeline() -> PipelineJSON:
    return PIPELINE
