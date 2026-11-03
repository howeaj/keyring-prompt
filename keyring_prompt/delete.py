"""Delete password entries from the system keyring."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from . import delete_password


def main(argv: Sequence[str] | None = None) -> None:
    """Delete every requested password entry without exposing its value."""
    parser = argparse.ArgumentParser(
        description="Delete one or more password entries from the system keyring."
    )
    parser.add_argument("service", nargs="+", help="keyring service name to delete")
    args = parser.parse_args(argv)
    for service in args.service:
        delete_password(service)
