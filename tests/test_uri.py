from uuid import uuid4

import pytest

from zmglue.models import URI, CommBackend, Protocol, URILocation, ZMQAddress


@pytest.fixture
def uribase_instance():
    hostname = "12.123.45.123"
    port = 1234
    id = uuid4()
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
        address=address,
    )


def test_to_uri(uribase_instance):
    expected_uri = f"zmq://{uribase_instance.hostname}/{uribase_instance.location.value}/{uribase_instance.id}?address=tcp%3A%2F%2F%3Fhostname%3D12.123.45.123%26port%3D1234"
    assert uribase_instance.to_uri() == expected_uri


def test_from_uri(uribase_instance):
    uri = uribase_instance.to_uri()
    reconstructed_instance = URI.from_uri(uri)
    assert reconstructed_instance.hostname == uribase_instance.hostname
    assert reconstructed_instance.address
    assert reconstructed_instance.address.hostname == uribase_instance.address.hostname
    assert reconstructed_instance.address.port == uribase_instance.address.port
    assert (
        reconstructed_instance.address.interface == uribase_instance.address.interface
    )


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
        ValueError, match="tcp protocol requires hostname and port to be set."
    ):
        ZMQAddress(protocol=Protocol.tcp, hostname=None, port=None)

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
        address=None,
    )
    expected_uri = f"zmq://{uri_base.hostname}/{uri_base.location.value}/{uri_base.id}"
    assert uri_base.to_uri() == expected_uri


def test_invalid_UUID():
    with pytest.raises(ValueError, match="badly formed hexadecimal UUID string"):
        URI.from_uri("zmq:///port/X24533?address=tcp%3A%2F%2F12.123.45.123%3A1234")


def test_uribase_from_uri_no_address():
    uri = f"zmq://example.com/port/{uuid4()}"
    reconstructed_instance = URI.from_uri(uri)
    assert reconstructed_instance.hostname == "example.com"
    assert reconstructed_instance.address is None
    assert reconstructed_instance.comm_backend == CommBackend.ZMQ
