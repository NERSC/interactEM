import difflib
from pprint import pformat
from uuid import UUID

import pytest

from zmglue.orchestrator import Orchestrator
from zmglue.pipeline import Pipeline
from zmglue.types import (
    CommBackend,
    PipelineJSON,
    PipelineMessage,
    URIConnectMessage,
    URIConnectResponseMessage,
    URILocation,
    URIUpdateMessage,
)


def test_handle_pipeline_request(orchestrator: Orchestrator, pipeline: PipelineJSON):
    msg = PipelineMessage()
    response = orchestrator.handle_pipeline_request(msg)
    assert isinstance(response, PipelineMessage)
    assert isinstance(response.pipeline, PipelineJSON)

    response_pipeline = Pipeline.from_pipeline(response.pipeline)
    expected_pipeline = Pipeline.from_pipeline(pipeline)

    assert response_pipeline == expected_pipeline

    def diff_pipelines(pipeline1, pipeline2):
        str1 = pformat(pipeline1)
        str2 = pformat(pipeline2)
        diff = difflib.unified_diff(str1.splitlines(), str2.splitlines(), lineterm="")
        return "\n".join(diff)

    response_json = response_pipeline.to_json().model_dump()
    expected_json = expected_pipeline.to_json().model_dump()

    assert (
        response_json == expected_json
    ), f"Differences:\n{diff_pipelines(response_json, expected_json)}"


def test_handle_uri_update_request(orchestrator: Orchestrator, operator_0_id: UUID):
    msg = URIUpdateMessage(
        id=operator_0_id,
        location=URILocation.operator,
        hostname="john",
        comm_backend=CommBackend.MPI,
    )
    response = orchestrator.handle_uri_update_request(msg)
    assert response.id == operator_0_id
    assert response.location == URILocation.operator
    assert response.hostname == "john"
    assert response.comm_backend == CommBackend.MPI


def test_handle_uri_connect_request(
    orchestrator: Orchestrator,
    operator_1_input_0_id: UUID,
    operator_0_output_0_id: UUID,
):
    msg = URIUpdateMessage(
        id=operator_0_output_0_id,
        location=URILocation.operator,
        hostname="john",
        comm_backend=CommBackend.MPI,
    )
    response = orchestrator.handle_uri_update_request(msg)

    msg = URIConnectMessage(id=operator_1_input_0_id)
    response = orchestrator.handle_uri_connect_request(msg)
    assert isinstance(response, URIConnectResponseMessage)
    assert response.connections[0].id == operator_0_output_0_id
    assert response.connections[0].hostname == "john"
