"""Launch a command after resolving selected environment variables from keyring."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from collections.abc import Sequence

from . import NoCredentialsError, get_password


def _password_env(value: str) -> tuple[str, str]:
    """Parse an ``ENVIRONMENT_VARIABLE=keyring-service`` assignment."""
    (name, separator, service) = value.partition("=")
    if not separator or not name or not service:
        raise argparse.ArgumentTypeError(
            "expected ENVIRONMENT_VARIABLE=keyring-service"
        )
    if not name.replace("_", "").isalnum() or name[0].isdigit():
        raise argparse.ArgumentTypeError(f"environment variable name '{name}' is invalid")
    return (name, service)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Resolve values from the system keyring, then replace this process "
            "with a command that receives them as environment variables."
        )
    )
    parser.add_argument(
        "--env",
        action="append",
        type=_password_env,
        default=[],
        metavar="ENVIRONMENT_VARIABLE=KEYRING_SERVICE",
        help="resolve a 'password' value stored in the keyring into an environment variable; may be repeated",
    )
    parser.add_argument(
        "--prompt",
        choices=("gui", "cli", "none"),
        default="gui",
        help="how to handle a missing keyring entry (default: gui)",
    )
    parser.add_argument(
        "--msg",
        action="append",
        default=[],
        metavar="MESSAGE",
        help="custom message for the corresponding --env prompt; may be repeated",
    )
    parser.add_argument(
        "command",
        nargs=argparse.REMAINDER,
        help="command to run; prefix it with ' -- '",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> None:
    """Resolve configured secrets and exec the requested child command."""
    parser = _parser()
    args = parser.parse_args(argv)
    command = args.command
    if command[:1] == ["--"]:
        command = command[1:]
    if not command:
        parser.error("a command is required after --")
    if args.msg and len(args.msg) != len(args.env):
        parser.error("provide one --msg for each --env, or omit --msg")

    prompt = None if args.prompt == "none" else args.prompt
    try:
        messages = args.msg or [None] * len(args.env)
        for (environment_variable, service), message in zip(args.env, messages):
            os.environ[environment_variable] = get_password(
                service,
                prompt=prompt,
                env_var=environment_variable,
                message=message,
            )
    except NoCredentialsError as error:
        parser.error(str(error))

    try:
        if sys.platform == "win32":
            # os.exec* on Windows spawns a new process and exits this one, so the
            # caller loses its stdio pipes. Run the command as a child instead.
            sys.exit(subprocess.call(command))
        else:
            os.execvp(command[0], command)
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"{str(exc)} '{command[0]}'") from None
