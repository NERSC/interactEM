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

module load conda
conda activate interactem
srun --nodes=2 --ntasks-per-node=1 dotenv -f /path/to/.env/file run interactem-agent