"""
Functional tests for pip's --require-virtualenv CLI flag.

These tests validate end-to-end CLI behavior through subprocess execution,
ensuring that the --require-virtualenv flag properly enforces virtual
environment presence when specified.
"""
import textwrap

import pytest

from pip._internal.cli.status_codes import SUCCESS, VIRTUALENV_NOT_FOUND

from tests.lib import PipTestEnvironment, create_basic_wheel_for_package
from tests.lib.venv import VirtualEnvironment


@pytest.fixture
def patch_not_in_virtualenv(virtualenv: VirtualEnvironment) -> None:
    """
    Fixture that patches running_under_virtualenv() to return False.
    
    This simulates running pip outside a virtual environment without
    actually modifying the test environment. Uses sitecustomize pattern
    to inject the patch into the subprocess pip execution.
    """
    virtualenv.sitecustomize = textwrap.dedent(
        """\
        from pip._internal.utils import virtualenv as venv_utils
        
        def fake_running_under_virtualenv():
            return False
        
        venv_utils.running_under_virtualenv = fake_running_under_virtualenv
        """
    )


class TestInstallRequireVirtualenv:
    """
    Test the install command's behavior with --require-virtualenv flag.
    
    Validates that pip install properly enforces virtualenv requirement
    when the flag is set, and proceeds normally without it.
    """

    def test_install_fails_outside_venv_with_flag(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that pip install --require-virtualenv fails outside virtualenv.
        
        When running outside a virtual environment with --require-virtualenv,
        pip should exit with code 3 (VIRTUALENV_NOT_FOUND) and display an
        appropriate error message.
        """
        result = script.pip(
            "install",
            "--require-virtualenv",
            "pip",
            expect_error=True,
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr

    def test_install_succeeds_inside_venv_with_flag(
        self,
        script: PipTestEnvironment,
    ) -> None:
        """
        Test that pip install --require-virtualenv succeeds inside virtualenv.
        
        When running inside a virtual environment (no patch applied), pip
        should proceed normally even with --require-virtualenv flag.
        """
        # Create a simple wheel package for testing
        wheel = create_basic_wheel_for_package(script, "test_package", "1.0")
        
        result = script.pip(
            "install",
            "--require-virtualenv",
            "--no-index",
            wheel.as_uri(),
        )
        
        assert result.returncode == SUCCESS
        assert "Successfully installed test_package-1.0" in result.stdout

    def test_install_succeeds_without_flag_outside_venv(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that pip install without --require-virtualenv succeeds outside venv.
        
        When the flag is not set, pip should proceed normally regardless of
        whether it's running in a virtual environment.
        """
        # Create a simple wheel package for testing
        wheel = create_basic_wheel_for_package(script, "test_package", "1.0")
        
        result = script.pip(
            "install",
            "--no-index",
            wheel.as_uri(),
        )
        
        assert result.returncode == SUCCESS
        assert "Successfully installed test_package-1.0" in result.stdout

    def test_error_message_appears_in_stderr(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that the correct error message appears in stderr when requirement violated.
        
        Validates that the exact expected error message is logged to stderr
        when pip is run with --require-virtualenv outside a virtual environment.
        """
        result = script.pip(
            "install",
            "--require-virtualenv",
            "pip",
            expect_error=True,
        )
        
        # Verify the exact error message is present
        assert "Could not find an activated virtualenv (required)." in result.stderr
        assert result.returncode == VIRTUALENV_NOT_FOUND


class TestMultipleCommandsRequireVirtualenv:
    """
    Test --require-virtualenv behavior across different pip commands.
    
    Validates that enforcing commands (install, download, wheel, uninstall)
    respect the requirement, while ignoring commands (cache, list, freeze)
    bypass it regardless of virtualenv presence.
    """

    def test_download_command_enforcement(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that pip download --require-virtualenv fails outside virtualenv.
        
        The download command is an enforcing command and should respect
        the --require-virtualenv flag.
        """
        result = script.pip(
            "download",
            "--require-virtualenv",
            "--no-index",
            "pip",
            expect_error=True,
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr

    def test_wheel_command_enforcement(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that pip wheel --require-virtualenv fails outside virtualenv.
        
        The wheel command is an enforcing command and should respect
        the --require-virtualenv flag.
        """
        # Create a simple package to build wheel from
        wheel = create_basic_wheel_for_package(script, "test_package", "1.0")
        
        result = script.pip(
            "wheel",
            "--require-virtualenv",
            "--no-index",
            wheel.as_uri(),
            expect_error=True,
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr

    def test_uninstall_command_enforcement(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that pip uninstall --require-virtualenv fails outside virtualenv.
        
        The uninstall command is an enforcing command and should respect
        the --require-virtualenv flag.
        """
        result = script.pip(
            "uninstall",
            "--require-virtualenv",
            "-y",
            "pip",
            expect_error=True,
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr

    def test_cache_command_ignores_requirement(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that pip cache --require-virtualenv succeeds outside virtualenv.
        
        The cache command has ignore_require_venv=True and should bypass
        the virtualenv requirement check even with the flag set.
        """
        result = script.pip(
            "cache",
            "list",
            "--require-virtualenv",
        )
        
        # Should succeed (exit code 0) even though we're "outside" a virtualenv
        assert result.returncode == SUCCESS

    def test_list_command_ignores_requirement(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that pip list --require-virtualenv succeeds outside virtualenv.
        
        The list command has ignore_require_venv=True and should bypass
        the virtualenv requirement check.
        """
        result = script.pip(
            "list",
            "--require-virtualenv",
        )
        
        assert result.returncode == SUCCESS

    def test_freeze_command_ignores_requirement(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that pip freeze --require-virtualenv succeeds outside virtualenv.
        
        The freeze command has ignore_require_venv=True and should bypass
        the virtualenv requirement check.
        """
        result = script.pip(
            "freeze",
            "--require-virtualenv",
        )
        
        assert result.returncode == SUCCESS


class TestRequireVirtualenvEnvironmentVar:
    """
    Test PIP_REQUIRE_VIRTUALENV environment variable integration.
    
    Validates that the PIP_REQUIRE_VIRTUALENV environment variable
    properly enables the virtualenv requirement, and that CLI flags
    can override environment variable settings.
    """

    def test_env_var_enforces_requirement(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that PIP_REQUIRE_VIRTUALENV=1 enforces the requirement.
        
        When the environment variable is set, pip should enforce the
        virtualenv requirement even without the CLI flag.
        """
        # Set the environment variable
        script.environ["PIP_REQUIRE_VIRTUALENV"] = "1"
        
        result = script.pip(
            "install",
            "pip",
            expect_error=True,
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr

    def test_cli_flag_overrides_env_var(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that CLI flag --require-virtualenv overrides env var setting.
        
        The CLI flag should take precedence over the environment variable.
        When the CLI flag is explicitly set, it should enforce the requirement
        regardless of the environment variable value.
        """
        # Set environment variable to false (or any value that might be interpreted as false)
        script.environ["PIP_REQUIRE_VIRTUALENV"] = "0"
        
        # CLI flag should still enforce the requirement
        result = script.pip(
            "install",
            "--require-virtualenv",
            "pip",
            expect_error=True,
        )
        
        assert result.returncode == VIRTUALENV_NOT_FOUND
        assert "Could not find an activated virtualenv (required)." in result.stderr

    def test_env_var_with_ignoring_command(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test that ignoring commands bypass requirement even with env var set.
        
        Commands with ignore_require_venv=True should bypass the check
        even when PIP_REQUIRE_VIRTUALENV environment variable is set.
        """
        script.environ["PIP_REQUIRE_VIRTUALENV"] = "1"
        
        result = script.pip(
            "cache",
            "list",
        )
        
        # Cache command should succeed despite env var
        assert result.returncode == SUCCESS

    def test_env_var_true_string_values(
        self,
        script: PipTestEnvironment,
        patch_not_in_virtualenv: None,
    ) -> None:
        """
        Test various truthy string values for PIP_REQUIRE_VIRTUALENV.
        
        The environment variable should accept various string representations
        of true values (1, true, yes, etc.) and enforce the requirement.
        """
        for true_value in ["1", "true", "yes"]:
            script.environ["PIP_REQUIRE_VIRTUALENV"] = true_value
            
            result = script.pip(
                "install",
                "pip",
                expect_error=True,
            )
            
            assert result.returncode == VIRTUALENV_NOT_FOUND, (
                f"Failed for env var value: {true_value}"
            )
            assert "Could not find an activated virtualenv (required)." in result.stderr

    def test_env_var_false_with_venv_present(
        self,
        script: PipTestEnvironment,
    ) -> None:
        """
        Test that PIP_REQUIRE_VIRTUALENV=0 does not enforce requirement.
        
        When the environment variable is explicitly set to a false value,
        pip should proceed normally without enforcing the virtualenv requirement.
        Running inside an actual virtualenv (no patch), this should succeed.
        """
        script.environ["PIP_REQUIRE_VIRTUALENV"] = "0"
        
        # Create a simple wheel package for testing
        wheel = create_basic_wheel_for_package(script, "test_package", "1.0")
        
        result = script.pip(
            "install",
            "--no-index",
            wheel.as_uri(),
        )
        
        assert result.returncode == SUCCESS
        assert "Successfully installed test_package-1.0" in result.stdout
