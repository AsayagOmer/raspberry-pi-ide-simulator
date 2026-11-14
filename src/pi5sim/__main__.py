"""Entry point used by the VS Code extension: python -m pi5sim <workspace-folder>."""
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# The protocol owns stdout; anything else printed by libraries goes to stderr.
_proto_out = open(sys.stdout.fileno(), "w", encoding="utf-8", buffering=1, closefd=False)
_proto_in = open(sys.stdin.fileno(), "r", encoding="utf-8", closefd=False)
sys.stdout = sys.stderr

from pi5sim.backend import Backend  # noqa: E402

if __name__ == "__main__":
    Backend(sys.argv[1] if len(sys.argv) > 1 else os.getcwd(), out=_proto_out).serve(_proto_in)
