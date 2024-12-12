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

    # Test push with header and data
    header = "text|5"
    data = bytearray(b"Hello")
    qclient.push(header, data)
    msg: thallium.Message = qprov.pull()
    assert msg.header == header
    assert bytearray(msg.data) == data

    # Test push_rdma with header and data
    header = "text|6"
    data = bytearray(b"Hello2")
    qclient.push_rdma(header, data)
    msg = qprov.pull()
    assert msg.header == header
    assert bytearray(msg.data) == data
