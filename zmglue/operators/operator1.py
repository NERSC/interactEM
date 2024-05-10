import argparse
from uuid import UUID

from zmglue.messenger import InterOperatorMessenger

parser = argparse.ArgumentParser()
parser.add_argument("--node-id", type=UUID, required=True)
args = parser.parse_args()


if __name__ == "__main__":
    node_id: UUID = args.node_id
    InterOperatorMessenger(node_id).start()
    
