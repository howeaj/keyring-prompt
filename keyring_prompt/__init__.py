"""Receive user credentials and cache in system keyring for subsequent use.

    First attempts to retrieve from keyring.
    If this fails, attempts to retrieve from env vars (the expected creds location in CI).
    If this fails, requests user entry and saves in keyring.
    If the credentials are rejected by the service, you should call delete_* to remove them from keyring.

    Example usage:
        is_ci = hasattr(os.environ, "TEAMCITY_VERSION")
        prompt = None if is_ci else "gui"
        cred_name = "MyCoolApp:https://someservice"
        creds = get_credential(cred_name, prompt=prompt, env_vars=("SOMESERVICE_USER", "SOMESERVICE_TOKEN"))
        try:
            someservice.login(creds.username, creds.password)
        except AuthorizationError:
            delete_credential(cred_name)

    Copyright (c) 2026 Andrew Howe. All Rights Reserved. See LICENSE (MIT).
"""

import contextlib
import getpass
import logging
import os
import re
import sys
from typing import Optional
import warnings

try:
    import readline
except ImportError:
    warnings.warn("readline not available; can't pre-fill username at cli", ImportWarning)

try:
    import tkinter as tk
    import tkinter.simpledialog
except ImportError:
    warnings.warn("TKinter not available; can't request creds via GUI", ImportWarning)

import keyring
from keyring.credentials import SimpleCredential


logger = logging.getLogger("keyring_prompt")


_USER = None  # username for keyring functions; unused


class NoCredentialsError(Exception):
    """Exception raised when no credentials could be returned."""


def _env_var(service: str) -> str:
    """Convert a keyring service name to a valid environment variable name."""
    sanitized_service = re.sub(r'[^A-Za-z0-9_]', '_', service)
    return f"PY_KEYRING_{sanitized_service}"


def _askstring(*args, **kwargs) -> str | None:
    """Wrapper for tkinter.simpledialog.askstring()."""
    tk.Tk().withdraw()
    return tkinter.simpledialog.askstring(*args, **kwargs)


def _get_username_gui(service: str) -> str | None:
    """Request username via a GUI popup. Returns None if they cancelled."""
    return _askstring("Username", f"Username for {service}: ", initialvalue=getpass.getuser())


def _get_password_gui(service: str) -> str | None:
    """Request username via a GUI popup. Returns None if they cancelled."""
    return _askstring("Password", f"Password for {service}: ", show='*')


def _get_username_cli(service: str) -> str:
    """Prompt the user to input a username at commandline."""
    can_prefill = "readline" in sys.modules
    if can_prefill:
        def _hook():
            readline.insert_text(getpass.getuser())
            readline.redisplay()
        readline.set_pre_input_hook(_hook)

    result = input(f"Username for {service}: ")

    if can_prefill:
        readline.set_pre_input_hook()

    return result


def _get_password_cli(service: str) -> str:
    """Prompt the user to input a password at commandline."""
    if sys.version_info >= (3, 14):
        password = getpass.getpass(prompt=f"Password for {service}:", echo_char="*")
    else:  # mask not available
        password = getpass.getpass(prompt=f"Password for {service}:")
    return password


def _get_credential(service: str, *, prompt: Optional[str]="gui", env_vars: Optional[tuple[str, str]]=("",""),
                    passonly: str="") -> SimpleCredential:
    """Shared implementation for get_credential() and get_password().

    See those functions for full docs.

    Give passonly="whatever" to ignore the username and only get a password.
    """
    if prompt not in ("cli", "gui", None):
        raise ValueError(f"prompt must be 'cli', 'gui' or None")

    credential = None

    service_user = service + "_USER"
    service_pass = service + ("" if passonly else "_PASS")

    # try keyring
    username = passonly or keyring.get_password(service_user, _USER)
    password = keyring.get_password(service_pass, _USER)
    if username and password:
        credential = SimpleCredential(username, password)
        logger.debug(f"Found credential for {service} in keyring")

    # try env vars
    if (credential is None) and (env_vars is not None):
        env_var_user = env_vars[0] or _env_var(service_user)
        env_var_msg_user = ("" if passonly else f" and {env_var_user}")
        username = passonly or os.environ.get(env_var_user, "")
        env_var_pass = env_vars[1] or _env_var(service_pass)
        password = os.environ.get(env_var_pass, "")
        if username and password:
            credential = SimpleCredential(username, password)
            logger.debug(f"Found credential for {service} in env var {env_var_pass}{env_var_msg_user}")

    # try interactive user prompt
    if credential is None:
        if prompt is None:
            service_msg_user = ("" if passonly else f" and {service_user}")
            msg = f"Credential not found for service {service_pass}{service_msg_user} in credential store"
            if env_vars is not None:
                msg += f" or env var {env_var_pass}{env_var_msg_user}"
            raise NoCredentialsError(msg)
        else:
            if prompt == "cli":
                username = passonly or _get_username_cli(service)
                password = _get_password_cli(service)
            else:
                assert(prompt == "gui")
                username = passonly or _get_username_gui(service)
                password = _get_password_gui(service)
            if None in (username, password):
                raise NoCredentialsError("User cancelled credentials input prompt")

            credential = SimpleCredential(username, password)

            # save to keyring
            if not passonly:
                keyring.set_password(service_user, _USER, username)
            keyring.set_password(service_pass, _USER, password)
            logger.debug(f"Saved credential for {service} in keyring")

    return credential


def get_credential(service: str, *, prompt: Optional[str]="gui",
                   env_vars: Optional[tuple[str, str]]=("","")) -> SimpleCredential:
    """Get a Credential object (with username and password fields) for `service`.

    First tries keyring, then env vars, then prompts the user.

    Args:
        service: The name of the keyring entry.
                 Two keyring entries will actually be used, with "_USER" and "_PASS" suffixes.
        prompt:  If "gui" (default) or "cli" and the password isn't available,
                 prompts the user to enter it (via cli or gui) and saves it in keyring.
                 None to disable prompting.
        env_vars: Optional custom environment variable names (user, pass) to try after keyring.
                  For any empty string, env vars based on `service` are tried:
                  "PY_KEYRING_{service}_{USER|PASS}" with non-alphanumerics replaced with underscores.
                  If this is None, no env vars are tried.

    Raises:
        NoCredentialsError: If no credentials could be obtained.
    """
    return _get_credential(service, prompt=prompt, env_vars=env_vars)


def get_password(service: str, *, prompt: Optional[str]="gui", env_var: Optional[str]="") -> str:
    """Get a password; first tries keyring, then an env var, then prompts the user.

    Args:
        service: The name of the keyring entry.
        prompt: If "gui" (default) or "cli" and the password isn't available,
                prompts the user to enter it (via cli or gui) and saves it in keyring.
                None to disable prompting.
        env_var: Optional custom environment variable name to try after keyring.
                 If this is the empty string, an env var based on `service` is tried:
                 "PY_KEYRING_{service}" with non-alphanumerics replaced with underscores.
                 If this is None, no env vars are tried.

    Raises:
        NoCredentialsError: If no password could be found.
    """
    env_vars = None if env_var is None else ("", env_var)
    creds = _get_credential(service, prompt=prompt, env_vars=env_vars, passonly="passonly")
    return creds.password


def _delete_keyring_entry(service):
    """Shared implementation for delete_credential() and delete_password()."""
    try:
        keyring.delete_password(service, _USER)
    except keyring.errors.PasswordDeleteError:
        logger.warning(f"Failed to delete {service} from keyring (it may not have been there in the first place)")
    else:
        logger.debug(f"Deleted {service} from keyring")


def delete_credential(service: str):
    """Delete any credential for `service` stored in keyring."""
    for suffix in ("USER", "PASS"):
        _delete_keyring_entry(f"{service}_{suffix}")


def delete_password(service: str):
    """Delete any password for `service` stored in keyring."""
    _delete_keyring_entry(service)


@contextlib.contextmanager
def with_password(service: str, *, exc_type: type | tuple[type] = Exception, **kwargs) -> str:
    """Contextmanager that yields the password for `service`, and deletes it if the context raises `exc_type`.

    Args:
        service: The name of the keyring entry.
        exc_type: Either a single subclass of Exception, or a tuple of several,
                  which should cause any obtained password to be deleted from the credential store.
        kwargs: passed through to `get_password()`
    """

    password = get_password(service, **kwargs)
    try:
        yield password
    except exc_type:
        delete_password(service)
