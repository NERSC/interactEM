import numpy as np
import zmq
from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()

if rank == 0:

    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.bind("tcp://localhost:5555")
    port_name = socket.recv_string()

    # Connect to the server
    intercomm = MPI.COMM_WORLD.Connect(port_name, info=MPI.INFO_NULL, root=0)

    # Create and send the array
    data = np.empty(10, dtype="d")
    intercomm.Recv(data, source=0, tag=0)
    print("Received array:", data)

    intercomm.Disconnect()
else:
    print("This script should be run with a single process only.")