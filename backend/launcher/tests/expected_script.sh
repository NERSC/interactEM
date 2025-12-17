#!/bin/bash

# ██╗███╗   ██╗████████╗███████╗██████╗  █████╗  ██████╗████████╗███████╗███╗   ███╗
# ██║████╗  ██║╚══██╔══╝██╔════╝██╔══██╗██╔══██╗██╔════╝╚══██╔══╝██╔════╝████╗ ████║
# ██║██╔██╗ ██║   ██║   █████╗  ██████╔╝███████║██║        ██║   █████╗  ██╔████╔██║
# ██║██║╚██╗██║   ██║   ██╔══╝  ██╔══██╗██╔══██║██║        ██║   ██╔══╝  ██║╚██╔╝██║
# ██║██║ ╚████║   ██║   ███████╗██║  ██║██║  ██║╚██████╗   ██║   ███████╗██║ ╚═╝ ██║
# ╚═╝╚═╝  ╚═══╝   ╚═╝   ╚══════╝╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝   ╚═╝   ╚══════╝╚═╝     ╚═╝

#SBATCH --qos=normal
#SBATCH --constraint=gpu
#SBATCH --time=01:30:00 
#SBATCH --account=test_account
#SBATCH --nodes=2
#SBATCH --exclusive

export HDF5_USE_FILE_LOCKING=FALSE
cd /path/to/.env
srun --nodes=2 --ntasks-per-node=1 uv run --project /path/to/interactEM/backend/agent interactem-agent