from uuid import UUID, uuid4

import pytest
from interactem.core.models import URI, CommBackend, Protocol, URILocation, ZMQAddress


@pytest.fixture
def uribase_instance() -> URI:
    hostname = "12.123.45.123"
    port = 1234
    id = UUID("be7ec23d-04b4-42cf-bb4c-45480f809cc6")
    address = ZMQAddress(
        protocol=Protocol.tcp,
        hostname=hostname,
        port=port,
    )
    return URI(
        id=id,
        location=URILocation.port,
        hostname="example.com",
        comm_backend=CommBackend.ZMQ,
        query={"address": [address.to_address()]},
    )


def test_to_from_uri(uribase_instance: URI):
    uri = uribase_instance.to_uri()
    reconstructed_instance = URI.from_uri(uri)
    assert reconstructed_instance.hostname == uribase_instance.hostname
    assert reconstructed_instance.id == uribase_instance.id
    assert reconstructed_instance.location == uribase_instance.location
    assert reconstructed_instance.comm_backend == uribase_instance.comm_backend
    assert reconstructed_instance.query == uribase_instance.query


def test_from_to_uri(uribase_instance: URI):
    uri = "zmq://example.com/port/be7ec23d-04b4-42cf-bb4c-45480f809cc6?address=tcp%3A%2F%2F%3Fhostname%3D12.123.45.123%26port%3D1234"
    reconstructed_instance = URI.from_uri(uri)
    assert reconstructed_instance.hostname == uribase_instance.hostname
    assert reconstructed_instance.id == uribase_instance.id
    assert reconstructed_instance.location == uribase_instance.location
    assert reconstructed_instance.comm_backend == uribase_instance.comm_backend
    assert reconstructed_instance.query == uribase_instance.query
    assert reconstructed_instance.to_uri() == uri


def test_zmqaddress_tcp():
    address = ZMQAddress.from_address("tcp://?hostname=12.123.45.123&port=1234")
    assert address.protocol == Protocol.tcp
    assert address.hostname == "12.123.45.123"
    assert address.port == 1234
    assert address.to_address() == "tcp://?hostname=12.123.45.123&port=1234"
    assert address.to_connect_address() == "tcp://12.123.45.123:1234"


def test_zmqaddress_tcp_with_interface():
    address = ZMQAddress.from_address("tcp://?interface=eth0&port=1234")
    assert address.protocol == Protocol.tcp
    assert address.interface == "eth0"
    assert address.port == 1234
    assert address.to_address() == "tcp://?interface=eth0&port=1234"
    assert address.to_bind_address() == "tcp://eth0:1234"


def test_zmqaddress_inproc():
    address = ZMQAddress.from_address("inproc://my_endpoint/asdf")
    assert address.protocol == Protocol.inproc
    assert address.endpoint == "my_endpoint/asdf"
    assert address.to_address() == "inproc://my_endpoint/asdf"
    assert address.to_connect_address() == "inproc://my_endpoint/asdf"


def test_zmqaddress_inproc_uuid():
    id = uuid4()
    id_str = str(id)
    address = ZMQAddress.from_address(f"inproc://{id_str}")
    assert address.protocol == Protocol.inproc
    assert address.endpoint == id_str
    assert address.to_address() == f"inproc://{id_str}"
    assert address.to_connect_address() == f"inproc://{id_str}"


def test_zmqaddress_ipc():
    address = ZMQAddress.from_address("ipc://my_endpoint")
    assert address.protocol == Protocol.ipc
    assert address.endpoint == "my_endpoint"
    assert address.to_address() == "ipc://my_endpoint"
    assert address.to_connect_address() == "ipc://my_endpoint"


def test_zmqaddress_invalid_protocol():
    with pytest.raises(ValueError, match="Invalid address protocol."):
        ZMQAddress.from_address("ftp://12.123.45.123:1234")


def test_zmqaddress_protocol_correctness():
    with pytest.raises(
        ValueError, match="inproc and ipc protocols require endpoint to be set."
    ):
        ZMQAddress(protocol=Protocol.inproc, hostname="hostname")


def test_uribase_no_address():
    uri_base = URI(
        id=uuid4(),
        location=URILocation.port,
        hostname="example.com",
        comm_backend=CommBackend.ZMQ,
    )
    expected_uri = f"zmq://{uri_base.hostname}/{uri_base.location.value}/{uri_base.id}"
    assert uri_base.to_uri() == expected_uri


def test_invalid_UUID():
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        URI.from_uri("zmq:///port/X24533?address=tcp%3A%2F%2F12.123.45.123%3A1234")


def test_uribase_from_uri_no_address():
    id = uuid4()
    uri = f"zmq://example.com/port/{id}"
    reconstructed_instance = URI.from_uri(uri)
    assert reconstructed_instance.hostname == "example.com"
    assert reconstructed_instance.comm_backend == CommBackend.ZMQ
    assert reconstructed_instance.location == URILocation.port
    assert reconstructed_instance.id == id
