import time

import numpy as np
import zmq
from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()

if rank == 0:
    # Receiver code
    context = zmq.Context()
    socket = context.socket(zmq.PULL)
    socket.bind("tcp://localhost:5555")
    port_name = socket.recv_string()
    print("Received port name:", port_name)

    # Connect to the server
    intercomm = comm.Connect(port_name, info=MPI.INFO_NULL, root=0)
    print("Connected to sender.")

    # Create an intra-communicator
    newcomm = intercomm.Merge(high=False)
    # Get and print the rank and size of the new communicator
    new_rank = newcomm.Get_rank()
    new_size = newcomm.Get_size()
    print(f"New communicator rank {new_rank} of {new_size}")

    # Create a window for the data to be received
    data = np.empty(10, dtype="d")
    win = MPI.Win.Create(data, comm=newcomm)

    # Lock the window to ensure it is ready for data reception

    newcomm.barrier()

    print("Received array:", data)

    win.Free()
    intercomm.Disconnect()
else:
    print("This script should be run with a single process only.")
