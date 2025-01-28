import sys

import numpy as np

import thallium


def test_ownership():
    engine_server = thallium.Engine("na+sm", thallium.EngineMode.SERVER)
    engine_client = thallium.Engine("na+sm", thallium.EngineMode.CLIENT)
    qprov = thallium.QueueProvider(engine_server, 1)
    qclient = thallium.QueueClient(engine_client, engine_server.address, 1)

    data = np.random.rand(5, 5)
    print(f"Python: Initial data refcount: {sys.getrefcount(data)}")

    msg = thallium.Message("test", data)
    print(f"Python: After Message creation refcount: {sys.getrefcount(data)}")
    qclient.push_rdma(msg)

    received_msg = qprov.pull()
    received_data = received_msg.data
    print(f"Python: Received data refcount: {sys.getrefcount(received_data)}")

    del msg
    print("Python: After deleting original message")
    print(f"Python: Original data refcount: {sys.getrefcount(data)}")
    print(f"Python: Received data refcount: {sys.getrefcount(received_data)}")

    del received_msg
    print("Python: After deleting received message")
    print(f"Python: Original data refcount: {sys.getrefcount(data)}")
    print(f"Python: Received data refcount: {sys.getrefcount(received_data)}")

    print(data)
    print(received_data)

    # Clean up
    del data
    del received_data


if __name__ == "__main__":
    test_ownership()
