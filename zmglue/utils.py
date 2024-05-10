import socket as libsocket


def find_free_port() -> int:
    with libsocket.socket(libsocket.AF_INET, libsocket.SOCK_STREAM) as s:
        s.bind(("", 0))
        s.setsockopt(libsocket.SOL_SOCKET, libsocket.SO_REUSEADDR, 1)
        return s.getsockname()[1]
