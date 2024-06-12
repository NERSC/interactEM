from uuid import UUID

import pytest

from zmglue.fixtures import (
    OPERATOR_0_ID,
    OPERATOR_0_OUTPUT_0_ID,
    OPERATOR_0_OUTPUT_1_ID,
    OPERATOR_1_ID,
    OPERATOR_1_INPUT_0_ID,
    OPERATOR_2_ID,
    OPERATOR_2_INPUT_0_ID,
    PIPELINE_ID,
)
from zmglue.models import (
    CommBackend,
    EdgeJSON,
    OperatorJSON,
    PipelineJSON,
    PortJSON,
    PortType,
    URIBase,
    URILocation,
)


@pytest.fixture(scope="module")
def operator_0_id() -> UUID:
    return OPERATOR_0_ID


@pytest.fixture(scope="module")
def operator_1_id() -> UUID:
    return OPERATOR_1_ID


@pytest.fixture(scope="module")
def operator_2_id() -> UUID:
    return OPERATOR_2_ID


@pytest.fixture(scope="module")
def operator_0_output_0_id() -> UUID:
    return OPERATOR_0_OUTPUT_0_ID


@pytest.fixture(scope="module")
def operator_0_output_1_id() -> UUID:
    return OPERATOR_0_OUTPUT_1_ID


@pytest.fixture(scope="module")
def operator_1_input_0_id() -> UUID:
    return OPERATOR_1_INPUT_0_ID


@pytest.fixture(scope="module")
def operator_2_input_0_id() -> UUID:
    return OPERATOR_2_INPUT_0_ID


@pytest.fixture(scope="module")
def operator_0(
    operator_0_id: UUID, operator_0_output_0_id: UUID, operator_0_output_1_id: UUID
) -> OperatorJSON:
    return OperatorJSON(
        id=operator_0_id,
        params={"hello": "world"},
        outputs=[operator_0_output_0_id, operator_0_output_1_id],
        uri=URIBase(
            id=operator_0_id,
            comm_backend=CommBackend.ZMQ,
            location=URILocation.operator,
            hostname="localhost",
        ),
    )


@pytest.fixture(scope="module")
def operator_0_port_0(operator_0_id: UUID, operator_0_output_0_id: UUID) -> PortJSON:
    return PortJSON(
        id=operator_0_output_0_id,
        operator_id=operator_0_id,
        port_type=PortType.output,
        portkey="out1",
        uri=URIBase(
            id=operator_0_output_0_id,
            comm_backend=CommBackend.ZMQ,
            location=URILocation.port,
            hostname="localhost",
        ),
    )


@pytest.fixture(scope="module")
def operator_0_port_1(operator_0_id: UUID, operator_0_output_1_id: UUID) -> PortJSON:
    return PortJSON(
        id=operator_0_output_1_id,
        operator_id=operator_0_id,
        port_type=PortType.output,
        portkey="out1",
        uri=URIBase(
            id=operator_0_output_1_id,
            comm_backend=CommBackend.ZMQ,
            location=URILocation.port,
            hostname="localhost",
        ),
    )


@pytest.fixture(scope="module")
def operator_1(operator_1_id: UUID, operator_1_input_0_id: UUID) -> OperatorJSON:
    return OperatorJSON(
        id=operator_1_id,
        params={"hello": "world"},
        inputs=[operator_1_input_0_id],
        uri=URIBase(
            id=operator_1_id,
            comm_backend=CommBackend.ZMQ,
            location=URILocation.operator,
            hostname="localhost",
        ),
    )


@pytest.fixture(scope="module")
def operator_1_port_0(operator_1_id: UUID, operator_1_input_0_id: UUID) -> PortJSON:
    return PortJSON(
        id=operator_1_input_0_id,
        operator_id=operator_1_id,
        port_type=PortType.input,
        portkey="in1",
        uri=URIBase(
            id=operator_1_input_0_id,
            comm_backend=CommBackend.ZMQ,
            location=URILocation.port,
            hostname="localhost",
        ),
    )


@pytest.fixture(scope="module")
def operator_2(operator_2_id: UUID, operator_2_input_0_id: UUID) -> OperatorJSON:
    return OperatorJSON(
        id=operator_2_id,
        params={"hello": "world"},
        inputs=[operator_2_input_0_id],
        uri=URIBase(
            id=operator_2_id,
            comm_backend=CommBackend.ZMQ,
            location=URILocation.operator,
            hostname="localhost",
        ),
    )


@pytest.fixture(scope="module")
def operator_2_port_0(operator_2_id: UUID, operator_2_input_0_id: UUID) -> PortJSON:
    return PortJSON(
        id=operator_2_input_0_id,
        operator_id=operator_2_id,
        port_type=PortType.input,
        portkey="in1",
        uri=URIBase(
            id=operator_2_input_0_id,
            comm_backend=CommBackend.ZMQ,
            location=URILocation.port,
            hostname="localhost",
        ),
    )


@pytest.fixture(scope="module")
def edge_0(operator_0_id: UUID, operator_0_output_0_id: UUID) -> EdgeJSON:
    return EdgeJSON(
        input_id=operator_0_id,
        output_id=operator_0_output_0_id,
    )


@pytest.fixture(scope="module")
def edge_1(operator_0_id: UUID, operator_0_output_1_id: UUID) -> EdgeJSON:
    return EdgeJSON(
        input_id=operator_0_id,
        output_id=operator_0_output_1_id,
    )


@pytest.fixture(scope="module")
def edge_2(operator_0_output_0_id: UUID, operator_1_input_0_id: UUID) -> EdgeJSON:
    return EdgeJSON(
        input_id=operator_0_output_0_id,
        output_id=operator_1_input_0_id,
    )


@pytest.fixture(scope="module")
def edge_3(operator_0_output_1_id: UUID, operator_2_input_0_id: UUID) -> EdgeJSON:
    return EdgeJSON(
        input_id=operator_0_output_1_id,
        output_id=operator_2_input_0_id,
    )


@pytest.fixture(scope="module")
def edge_4(operator_1_input_0_id: UUID, operator_1_id: UUID) -> EdgeJSON:
    return EdgeJSON(
        input_id=operator_1_input_0_id,
        output_id=operator_1_id,
    )


@pytest.fixture(scope="module")
def edge_5(operator_2_input_0_id: UUID, operator_2_id: UUID) -> EdgeJSON:
    return EdgeJSON(
        input_id=operator_2_input_0_id,
        output_id=operator_2_id,
    )


@pytest.fixture(scope="module")
def pipeline(
    operator_0: OperatorJSON,
    operator_1: OperatorJSON,
    operator_2: OperatorJSON,
    operator_0_port_0: PortJSON,
    operator_0_port_1: PortJSON,
    operator_1_port_0: PortJSON,
    operator_2_port_0: PortJSON,
    edge_0: EdgeJSON,
    edge_1: EdgeJSON,
    edge_2: EdgeJSON,
    edge_3: EdgeJSON,
    edge_4: EdgeJSON,
    edge_5: EdgeJSON,
) -> PipelineJSON:
    return PipelineJSON(
        id=PIPELINE_ID,
        operators=[operator_0, operator_1, operator_2],
        ports=[
            operator_0_port_0,
            operator_0_port_1,
            operator_1_port_0,
            operator_2_port_0,
        ],
        edges=[edge_0, edge_1, edge_2, edge_3, edge_4, edge_5],
    )
