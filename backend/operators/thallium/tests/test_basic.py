import re

import thallium


def test_queue_provider():
    qprov = thallium.QueueProvider("na+sm", 1)
    address = qprov.get_address()
    pattern = re.compile(r"^na\+sm://\d+-\d+$")
    assert pattern.match(
        address
    ), f"Address '{address}' does not match the expected format 'na+sm://XXX-YYY'"

    qclient = thallium.QueueClient("na+sm", address, 1)
    qclient.push("Hello")
    assert qprov.pull() == "Hello"

    qclient.push_rdma("Hello2")
    assert qprov.pull() == "Hello2"
