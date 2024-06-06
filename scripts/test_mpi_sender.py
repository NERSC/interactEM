import numpy as np
import zmq
from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()

if rank == 0:
    # The port name should be provided as a command line argument or through some IPC mechanism
    print("Client started...")
    info = MPI.INFO_NULL

    port_name = MPI.Open_port()
    # Set up ZeroMQ context and socket
    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    socket.connect("tcp://localhost:5555")
    socket.send_string(port_name)

    intercomm = MPI.COMM_WORLD.Accept(port_name, info=info, root=0)

    # Create and send the array
    data = np.arange(10, dtype="d")
    intercomm.Send(data, dest=0, tag=0)
    print("Sent array:", data)

    intercomm.Disconnect()
else:
    print("This script should be run with a single process only.")
