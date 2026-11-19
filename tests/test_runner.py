"""Tests for the command launcher."""

from __future__ import annotations

import argparse
import os
import unittest
from unittest.mock import patch

import keyring_prompt
from keyring_prompt import delete
from keyring_prompt import runner


class PasswordEnvironmentTest(unittest.TestCase):
    def test_parses_environment_variable_and_service(self) -> None:
        self.assertEqual(
            runner._password_env("TOKEN=example:service"),
            ("TOKEN", "example:service"),
        )

    def test_rejects_malformed_assignment(self) -> None:
        with self.assertRaises(argparse.ArgumentTypeError):
            runner._password_env("TOKEN")


class MainTest(unittest.TestCase):
    def setUp(self) -> None:
        self.platform = patch.object(runner.sys, "platform", "linux")
        self.platform.start()

    def tearDown(self) -> None:
        self.platform.stop()

    def test_resolves_password_then_executes_command(self) -> None:
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(runner, "get_password", return_value="secret") as get_password,
            patch.object(runner.os, "execvp") as execvp,
        ):
            runner.main(
                [
                    "--env",
                    "TOKEN=example:service",
                    "--",
                    "child-command",
                    "argument",
                ]
            )
            self.assertEqual(os.environ["TOKEN"], "secret")

        get_password.assert_called_once_with(
            "example:service", prompt="gui", env_var="TOKEN", message=None, title=None
        )
        execvp.assert_called_once_with("child-command", ["child-command", "argument"])

    def test_disables_prompt_when_requested(self) -> None:
        with (
            patch.object(runner, "get_password", return_value="secret") as get_password,
            patch.object(runner.os, "execvp"),
        ):
            runner.main(
                [
                    "--prompt",
                    "none",
                    "--env",
                    "TOKEN=example:service",
                    "--",
                    "child-command",
                ]
            )

        get_password.assert_called_once_with(
            "example:service", prompt=None, env_var="TOKEN", message=None, title=None
        )

    def test_passes_custom_prompt_message(self) -> None:
        with (
            patch.object(runner, "get_password", return_value="secret") as get_password,
            patch.object(runner.os, "execvp"),
        ):
            runner.main(
                [
                    "--msg",
                    "Enter the deployment token: ",
                    "--title",
                    "Deployment credentials",
                    "--env",
                    "TOKEN=example:service",
                    "--",
                    "child-command",
                ]
            )

        get_password.assert_called_once_with(
            "example:service",
            prompt="gui",
            env_var="TOKEN",
            message="Enter the deployment token: ",
            title="Deployment credentials",
        )

    def test_passes_messages_in_environment_variable_order(self) -> None:
        with (
            patch.object(runner, "get_password", return_value="secret") as get_password,
            patch.object(runner.os, "execvp"),
        ):
            runner.main(
                [
                    "--env",
                    "FIRST_TOKEN=first:service",
                    "--msg",
                    "Enter the first token: ",
                    "--title",
                    "Application credentials",
                    "--env",
                    "SECOND_TOKEN=second:service",
                    "--msg",
                    "Enter the second token: ",
                    "--",
                    "child-command",
                ]
            )

        self.assertEqual(
            get_password.call_args_list,
            [
                (
                    ("first:service",),
                    {
                        "prompt": "gui",
                        "env_var": "FIRST_TOKEN",
                        "message": "Enter the first token: ",
                        "title": "Application credentials",
                    },
                ),
                (
                    ("second:service",),
                    {
                        "prompt": "gui",
                        "env_var": "SECOND_TOKEN",
                        "message": "Enter the second token: ",
                        "title": "Application credentials",
                    },
                ),
            ],
        )


class PromptMessageTest(unittest.TestCase):
    def test_prepends_custom_message_to_cli_prompt(self) -> None:
        with patch.object(keyring_prompt.getpass, "getpass", return_value="secret") as getpass:
            keyring_prompt._get_password_cli("example:service", "Create a token at example.test")

        self.assertEqual(
            getpass.call_args.kwargs["prompt"],
            "Create a token at example.test\nPassword for example:service: ",
        )

    def test_prepends_custom_message_to_gui_prompt(self) -> None:
        with patch.object(keyring_prompt, "_string_dialog", return_value="secret") as string_dialog:
            keyring_prompt._get_password_gui("example:service", "Create a token at example.test")

        string_dialog.assert_called_once_with(
            "Password",
            "Create a token at example.test\n\nPassword for example:service: ",
            show="*",
        )

    def test_uses_custom_gui_dialog_title(self) -> None:
        with patch.object(keyring_prompt, "_string_dialog", return_value="secret") as string_dialog:
            keyring_prompt._get_password_gui("example:service", title="My application")

        string_dialog.assert_called_once_with(
            "My application",
            "Password for example:service: ",
            show="*",
        )


class PromptLinkTest(unittest.TestCase):
    def test_trims_sentence_punctuation_from_url(self) -> None:
        self.assertEqual(
            keyring_prompt._SelectableStringDialog._trim_url("https://example.test/token."),
            "https://example.test/token",
        )

    def test_opens_url_in_browser(self) -> None:
        with patch.object(keyring_prompt.webbrowser, "open_new_tab") as open_new_tab:
            result = keyring_prompt._SelectableStringDialog.open_url(
                None, "https://example.test/token"
            )

        self.assertEqual(result, "break")
        open_new_tab.assert_called_once_with("https://example.test/token")


class DeleteTest(unittest.TestCase):
    def test_deletes_each_requested_service(self) -> None:
        with patch.object(delete, "delete_password") as delete_password:
            delete.main(["first-service", "second-service"])

        self.assertEqual(
            delete_password.call_args_list,
            [
                (("first-service",), {}),
                (("second-service",), {}),
            ],
        )

