import socket as libsocket

import networkx as nx

from zmglue.types import EdgeJSON, NodeJSON, PipelineJSON


def find_free_port():
    with libsocket.socket(libsocket.AF_INET, libsocket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(libsocket.SOL_SOCKET, libsocket.SO_REUSEADDR, 1)
        return s.getsockname()[1], libsocket.gethostname()
