import numpy as np
import zmq
from mpi4py import MPI

comm = MPI.COMM_WORLD
rank = comm.Get_rank()

if rank == 0:
    # Sender code
    print("Client started...")
    info = MPI.INFO_NULL

    port_name = MPI.Open_port()
    print("Port opened:", port_name)

    # Set up ZeroMQ context and socket
    context = zmq.Context()
    socket = context.socket(zmq.PUSH)
    socket.connect("tcp://localhost:5555")
    socket.send_string(port_name)

    print("Port name sent to receiver.")

    intercomm = comm.Accept(port_name, info=info, root=0)
    print("Connection accepted by receiver.")

    # Create an intra-communicator
    newcomm = intercomm.Merge(high=True)

    # Get and print the rank and size of the new communicator
    new_rank = newcomm.Get_rank()
    new_size = newcomm.Get_size()
    print(f"New communicator rank {new_rank} of {new_size}")

    # Create the data to be sent
    data = np.arange(10, dtype="d")

    # Create a window with no local memory
    win = MPI.Win.Create(None, comm=newcomm)

    # Lock the receiver's window
    win.Lock_all()

    # Put the data into the receiver's window
    win.Put(data, target_rank=0)

    # Unlock the receiver's window
    win.Unlock_all()

    newcomm.barrier()

    print("Sent array:", data)

    win.Free()
    intercomm.Disconnect()
else:
    print("This script should be run with a single process only.")
