from uuid import UUID

from .models import EdgeJSON, OperatorJSON, PipelineJSON, PortJSON, PortType

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
    image="interactEM/operator",
    params={"hello": "world"},
    outputs=[OPERATOR_0_OUTPUT_0_ID, OPERATOR_0_OUTPUT_1_ID],
)

OPERATOR_0_PORT_0 = PortJSON(
    id=OPERATOR_0_OUTPUT_0_ID,
    operator_id=OPERATOR_0_ID,
    port_type=PortType.output,
    portkey="out1",
)

OPERATOR_0_PORT_1 = PortJSON(
    id=OPERATOR_0_OUTPUT_1_ID,
    operator_id=OPERATOR_0_ID,
    port_type=PortType.output,
    portkey="out1",
)

OPERATOR_1 = OperatorJSON(
    id=OPERATOR_1_ID,
    image="interactEM/operator",
    params={"hello": "world"},
    inputs=[OPERATOR_1_INPUT_0_ID],
)

OPERATOR_1_PORT_0 = PortJSON(
    id=OPERATOR_1_INPUT_0_ID,
    operator_id=OPERATOR_1_ID,
    port_type=PortType.input,
    portkey="in1",
)

OPERATOR_2 = OperatorJSON(
    id=OPERATOR_2_ID,
    image="interactEM/operator",
    params={"hello": "world"},
    inputs=[OPERATOR_2_INPUT_0_ID],
)

OPERATOR_2_PORT_0 = PortJSON(
    id=OPERATOR_2_INPUT_0_ID,
    operator_id=OPERATOR_2_ID,
    port_type=PortType.input,
    portkey="in1",
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
