keyring-prompt is a python package that wraps [keyring](https://pypi.org/project/keyring/),
providing simple interactive GUI or CLI user input for missing credentials.

A call to `get_password()` or `get_credential()`:
- First attempts to retrieve from keyring.
- If this fails, attempts to retrieve from environment variables (a typical alternative location for CI).
- If this fails, requests user entry and saves in keyring.

If the user-provided credentials are invalid, call `delete_password()` or `delete_credential()`
to clear them for re-entry on next attempt.

Installation:

    pip install keyring-prompt

Basic usage example:
```python
from keyring_prompt import delete_password, get_password

cred_name = "MyCoolApp:https://someservice"
token = get_password(cred_name)
try:
    someservice.login(token)
except AuthorizationError:
    delete_password(cred_name)
```

Advanced usage example:
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
except AuthorizationError:
    delete_credential(cred_name)
```
