#!/usr/bin/env python3
"""Send one JSON line to a Herdr socket and print the response line.

Used for workspace.move_block and agent.view.set/clear, which have no CLI.
"""

import socket
import sys

def main(argv):
    if len(argv) != 2 or not argv[1].startswith("/"):
        return 2
    payload = sys.stdin.buffer.read()
    if not payload.endswith(b"\n"):
        payload += b"\n"
    sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(argv[1])
    sock.sendall(payload)
    data = b""
    while b"\n" not in data:
        chunk = sock.recv(65536)
        if not chunk:
            return 3
        data += chunk
        if len(data) > 4 * 1024 * 1024:
            return 3
    sys.stdout.buffer.write(data.split(b"\n", 1)[0] + b"\n")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv))
    except OSError as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(3)
