"""Tests for FastStream launcher."""

import datetime
from unittest.mock import AsyncMock, patch

import pytest
from faststream.nats import TestNatsBroker
from sfapi_client._models import StatusValue
from sfapi_client.compute import Machine

from interactem.core.constants import SUBJECT_SFAPI_JOBS_SUBMIT
from interactem.launcher.faststream_launcher import broker
from interactem.sfapi_models import AgentCreateEvent, ComputeType, StatusRequest


@pytest.mark.asyncio
async def test_status_handler():
    """Test status request handling."""
    async with TestNatsBroker(broker) as test_broker:
        with patch('interactem.launcher.faststream_launcher.sfapi_client') as mock_client:
            # Mock the compute call
            mock_compute = AsyncMock()
            mock_compute.status = StatusValue.active
            mock_client.compute.return_value = mock_compute

            # Publish a status request
            await test_broker.publish(
                StatusRequest(machine=Machine.perlmutter),
                subject="sfapi.status"
            )

            # Verify the handler was called
            # Note: In real implementation, you'd check the response or mock calls


@pytest.mark.asyncio
async def test_job_submission():
    """Test job submission handling."""
    async with TestNatsBroker(broker) as test_broker:
        with patch('interactem.launcher.faststream_launcher.job_handler') as mock_handler:
            # Mock the job handler
            mock_handler.submit_job = AsyncMock()

            # Publish a job submission request
            await test_broker.publish(
                AgentCreateEvent(
                    machine=Machine.perlmutter,
                    duration=datetime.timedelta(hours=1),
                    compute_type=ComputeType.gpu,
                    num_nodes=1
                ),
                subject=SUBJECT_SFAPI_JOBS_SUBMIT
            )

            # Verify job handler was called
            mock_handler.submit_job.assert_called_once()


@pytest.mark.asyncio
async def test_job_submission_error_handling():
    """Test job submission error handling."""
    async with TestNatsBroker(broker) as test_broker:
        with patch('interactem.launcher.faststream_launcher.job_handler') as mock_handler:
            # Mock the job handler to raise an exception
            mock_handler.submit_job = AsyncMock(side_effect=Exception("Test error"))

            # Publish a job submission request
            await test_broker.publish(
                AgentCreateEvent(
                    machine=Machine.perlmutter,
                    duration=datetime.timedelta(hours=1),
                    compute_type=ComputeType.gpu,
                    num_nodes=1
                ),
                subject=SUBJECT_SFAPI_JOBS_SUBMIT
            )

            # Verify error was handled (in real implementation, check error notifications)
            mock_handler.submit_job.assert_called_once()
