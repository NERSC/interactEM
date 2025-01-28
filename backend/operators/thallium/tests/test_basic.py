import re

import numpy as np
import pytest

import thallium


@pytest.fixture
def engine_server():
    engine = thallium.Engine("na+sm", thallium.EngineMode.SERVER)
    yield engine
    # Cleanup if needed

@pytest.fixture
def engine_client():
    engine = thallium.Engine("na+sm", thallium.EngineMode.CLIENT)
    yield engine
    # Cleanup if needed


@pytest.fixture
def queue_provider(engine_server):
    return thallium.QueueProvider(engine_server, 1)


@pytest.fixture
def queue_client(engine_client, engine_server):
    address = engine_server.address
    pattern = re.compile(r"^na\+sm://\d+-\d+$")
    assert pattern.match(address), (
        f"Address '{address}' does not match the expected format 'na+sm://XXX-YYY'"
    )
    return thallium.QueueClient(engine_client, address, 1)


@pytest.fixture
def test_data(request):
    dtype = request.param
    if np.issubdtype(dtype, np.integer):
        data = np.random.randint(0, 100, (512, 512), dtype=dtype)
    elif np.issubdtype(dtype, np.floating):
        data = np.random.rand(512, 512).astype(dtype)
    elif dtype == np.bool_:
        data = np.random.choice([True, False], size=(512, 512))
    else:
        raise ValueError(f"Unsupported dtype: {dtype}")
    return data, dtype


@pytest.mark.parametrize(
    "test_data",
    [
        np.int8,
        np.int16,
        np.int32,
        np.int64,
        np.uint8,
        np.uint16,
        np.uint32,
        np.uint64,
        np.float32,
        np.float64,
        np.bool,
    ],
    indirect=True,
)
def test_queue_provider_with_dtype(test_data, queue_provider, queue_client):
    data, dtype = test_data
    header = f"text|{dtype}"

    # Create and send message
    msg = thallium.Message(header, data)

    queue_client.push_rdma(msg)

    # Receive and verify message
    received_msg = queue_provider.pull()

    assert received_msg.header == header
    assert np.all(received_msg.data == data)
    assert received_msg.data.dtype == data.dtype
