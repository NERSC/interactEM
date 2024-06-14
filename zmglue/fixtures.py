from uuid import UUID, uuid4

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

OPERATOR_0_ID = UUID("12345678-1234-1234-1234-1234567890ab")
OPERATOR_1_ID = UUID("12345678-1234-1234-1234-1234567890cd")
OPERATOR_2_ID = UUID("12345678-1234-1234-1234-1234567890ef")

OPERATOR_0_OUTPUT_0_ID = UUID("87654321-4321-4321-4321-1234567890ab")
OPERATOR_0_OUTPUT_1_ID = UUID("87654321-4321-4321-4321-1234567890cd")
OPERATOR_1_INPUT_0_ID = UUID("87654321-4321-4321-4321-1234567890ef")
OPERATOR_2_INPUT_0_ID = UUID("87654321-4321-4321-4321-1234567890ff")
PIPELINE_ID = UUID("87654321-4321-4321-4321-1234567890ae")

OPERATOR_0 = OperatorJSON(
    id=OPERATOR_0_ID,
    params={"hello": "world"},
    outputs=[OPERATOR_0_OUTPUT_0_ID, OPERATOR_0_OUTPUT_1_ID],
    uri=URIBase(
        id=OPERATOR_0_ID,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.operator,
        hostname="localhost",
    ),
)

OPERATOR_0_PORT_0 = PortJSON(
    id=OPERATOR_0_OUTPUT_0_ID,
    operator_id=OPERATOR_0_ID,
    port_type=PortType.output,
    portkey="out1",
    uri=URIBase(
        id=OPERATOR_0_OUTPUT_0_ID,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.port,
        hostname="localhost",
    ),
)

OPERATOR_0_PORT_1 = PortJSON(
    id=OPERATOR_0_OUTPUT_1_ID,
    operator_id=OPERATOR_0_ID,
    port_type=PortType.output,
    portkey="out1",
    uri=URIBase(
        id=OPERATOR_0_OUTPUT_1_ID,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.port,
        hostname="localhost",
    ),
)

OPERATOR_1 = OperatorJSON(
    id=OPERATOR_1_ID,
    params={"hello": "world"},
    inputs=[OPERATOR_1_INPUT_0_ID],
    uri=URIBase(
        id=OPERATOR_1_ID,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.operator,
        hostname="localhost",
    ),
)

OPERATOR_1_PORT_0 = PortJSON(
    id=OPERATOR_1_INPUT_0_ID,
    operator_id=OPERATOR_1_ID,
    port_type=PortType.input,
    portkey="in1",
    uri=URIBase(
        id=OPERATOR_1_INPUT_0_ID,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.port,
        hostname="localhost",
    ),
)

OPERATOR_2 = OperatorJSON(
    id=OPERATOR_2_ID,
    params={"hello": "world"},
    inputs=[OPERATOR_2_INPUT_0_ID],
    uri=URIBase(
        id=OPERATOR_2_ID,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.operator,
        hostname="localhost",
    ),
)

OPERATOR_2_PORT_0 = PortJSON(
    id=OPERATOR_2_INPUT_0_ID,
    operator_id=OPERATOR_2_ID,
    port_type=PortType.input,
    portkey="in1",
    uri=URIBase(
        id=OPERATOR_2_INPUT_0_ID,
        comm_backend=CommBackend.ZMQ,
        location=URILocation.port,
        hostname="localhost",
    ),
)

EDGE_0 = EdgeJSON(
    input_id=OPERATOR_0_ID,
    output_id=OPERATOR_0_OUTPUT_0_ID,
)

EDGE_1 = EdgeJSON(
    input_id=OPERATOR_0_ID,
    output_id=OPERATOR_0_OUTPUT_1_ID,
)

EDGE_2 = EdgeJSON(
    input_id=OPERATOR_0_OUTPUT_0_ID,
    output_id=OPERATOR_1_INPUT_0_ID,
)

EDGE_3 = EdgeJSON(
    input_id=OPERATOR_0_OUTPUT_1_ID, output_id=OPERATOR_2_INPUT_0_ID, num_connections=2
)

EDGE_4 = EdgeJSON(input_id=OPERATOR_1_INPUT_0_ID, output_id=OPERATOR_1_ID)

EDGE_5 = EdgeJSON(input_id=OPERATOR_2_INPUT_0_ID, output_id=OPERATOR_2_ID)


PIPELINE = PipelineJSON(
    id=PIPELINE_ID,
    operators=[OPERATOR_0, OPERATOR_1, OPERATOR_2],
    ports=[OPERATOR_0_PORT_0, OPERATOR_0_PORT_1, OPERATOR_1_PORT_0, OPERATOR_2_PORT_0],
    edges=[EDGE_0, EDGE_1, EDGE_2, EDGE_3, EDGE_4, EDGE_5],
)
