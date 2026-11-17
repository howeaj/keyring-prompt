keyring-prompt is a python package that wraps [keyring](https://pypi.org/project/keyring/),
providing simple interactive GUI or CLI user input for missing credentials.

A call to `get_password()` or `get_credential()`:
- First attempts to retrieve from keyring.
- If this fails, attempts to retrieve from environment variables (a typical alternative location for CI).
- If this fails, requests user entry and saves in keyring.

If the user-provided credentials are invalid, call `delete_password()` or `delete_credential()`
to clear them for re-entry on next attempt.

This package also provides command-line programs `keyring-prompt-run` and `keyring-prompt-delete`
to easily supply keyring credentials to other commands via environment variables.

Installation:

    pip install keyring-prompt


## Usage as a python import

### Basic usage example:
```python
from keyring_prompt import with_password

with with_password("MyCoolApp:https://someservice", exc_type=SomeServiceAuthorizationError) as token:
    someservice.login(token)
```

### Advanced usage example:
```python
import os
from keyring_prompt import delete_credential, get_credential

# Change the keyring backend to use gpg/pass instead of the default
import keyring
import keyring_pass  # pip install keyring-pass
keyring.set_keyring(keyring_pass.PasswordStoreBackend())

cred_name = "MyCoolApp:https://someservice"

# Disable prompts if running in a specific Continuous Integration server
# and use the cli prompt instead of the default gui
is_ci = hasattr(os.environ, "TEAMCITY_VERSION")
prompt = None if is_ci else "cli"

# Look for the username and password in specific environment variables
# instead of the default "PY_KEYRING_" + cred_name + "_USER"/"_PASS"
env_vars = ("SOMESERVICE_USER", "SOMESERVICE_TOKEN")

creds = get_credential(cred_name, prompt=prompt, env_vars=env_vars)
try:
    someservice.login(creds.username, creds.password)
except SomeServiceAuthorizationError:
    delete_credential(cred_name)
```


## Commandline usage

### `keyring-prompt-run`

`keyring-prompt-run` resolves one or more credentials,
assigns them to environment variables only in the child process environment,
and then replaces itself with that command.

It is useful for running programs that accept credentials only through environment variables.

```powershell
keyring-prompt-run `
  --env FOOBAR_USERNAME=username:something.com `
  --env FOOBAR_PASSWORD=password:something.com `
  -- something
```

For every credential, the command checks keyring first,
then the named environment variable,
then shows a prompt and stores the entered value in the keyring.

Use `--msg "Whatever: "` after each `--env` to prepend a message to that password prompt.
When requesting multiple credentials, provide one `--msg` for each `--env`, in the same order.

Use `--prompt cli` in headless environments to prompt on the commandline instead of gui,
or `--prompt none` in CI environments to fail rather than prompt.

### `keyring-prompt-delete`

```powershell
keyring-prompt-delete username:something.com password:something.com
```
