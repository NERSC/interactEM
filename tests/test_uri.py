from uuid import uuid4

import pytest

from zmglue.types import CommBackend, Protocol, URILocation, URIZmq, URIZmqPort


@pytest.fixture
def urizmq_instance():
    return URIZmq(
        id=uuid4(),
        location=URILocation.port,
        hostname="example.com",
        comm_backend=CommBackend.ZMQ,
        protocol=Protocol.tcp,
        port=1234,
        interface="eth0",
    )


@pytest.fixture
def urizmq_port_instance():
    return URIZmqPort(
        id=uuid4(),
        location=URILocation.port,
        hostname="example.com",
        protocol=Protocol.inproc,
        comm_backend=CommBackend.ZMQ,
        port=1234,
        portkey="data_port",
    )


def test_to_uri(urizmq_instance):
    expected_uri = f"zmq://{urizmq_instance.hostname}/{urizmq_instance.location.value}/{urizmq_instance.id}?protocol=tcp&port=1234&interface=eth0"
    assert urizmq_instance.to_uri() == expected_uri


def test_to_connect_address(urizmq_instance):
    expected_address = "tcp://example.com:1234"
    assert urizmq_instance.to_connect_address() == expected_address


def test_to_bind_address_with_interface(urizmq_instance):
    urizmq_instance.hostname_bind = None
    expected_address = "tcp://eth0:1234"
    assert urizmq_instance.to_bind_address() == expected_address


def test_to_bind_address_error(urizmq_instance):
    urizmq_instance.interface = None
    urizmq_instance.hostname_bind = None
    with pytest.raises(ValueError):
        urizmq_instance.to_bind_address()


def test_from_uri(urizmq_instance):
    uri = urizmq_instance.to_uri()
    reconstructed_instance = URIZmq.from_uri(uri)
    assert reconstructed_instance.hostname == urizmq_instance.hostname
    assert reconstructed_instance.port == urizmq_instance.port
    assert reconstructed_instance.interface == urizmq_instance.interface


def test_urizmq_port_to_uri(urizmq_port_instance):
    expected_uri = f"zmq://{urizmq_port_instance.hostname}/{urizmq_port_instance.location.value}/{urizmq_port_instance.id}?protocol=inproc&port=1234&portkey=data_port"
    assert urizmq_port_instance.to_uri() == expected_uri


def test_urizmq_port_from_uri(urizmq_port_instance):
    uri = urizmq_port_instance.to_uri()
    reconstructed_instance = URIZmqPort.from_uri(uri)
    assert reconstructed_instance.portkey == urizmq_port_instance.portkey
    assert isinstance(reconstructed_instance, URIZmqPort)
