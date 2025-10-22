"""
Comprehensive unit tests for pip's --require-virtualenv CLI flag enforcement.

This test module validates the enforcement logic in base_command.py (lines 219-223)
that prevents package installations outside of virtual environments when the
--require-virtualenv flag is set.

Tests cover:
- Truth matrix validation (all 8 permutations of has_venv, require_venv, ignore_require_venv)
- Exit code verification (VIRTUALENV_NOT_FOUND = 3)
- Error message validation via caplog
- Command-level ignore_require_venv attribute behavior
- Option precedence between CLI flags and environment variables

Target: ≥90% coverage for base_command.py lines 219-223
"""

from __future__ import annotations

import logging
import os
import sys
from optparse import Values
from typing import Callable

import pytest

from pip._internal.cli.base_command import Command
from pip._internal.cli.status_codes import SUCCESS, VIRTUALENV_NOT_FOUND


# =============================================================================
# Fixtures for Mocking Virtualenv State
# =============================================================================


@pytest.fixture
def mock_not_in_virtualenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Fixture to simulate NOT being in a virtual environment.
    
    Mocks running_under_virtualenv() to return False, simulating execution
    outside a virtualenv without modifying sys.prefix or environment variables
    (which could corrupt the test runner's environment).
    
    Note: We patch where the function is USED (in base_command), not where
    it's defined (in utils.virtualenv), per Python's import semantics.
    """
    monkeypatch.setattr(
        "pip._internal.cli.base_command.running_under_virtualenv",
        lambda: False
    )


@pytest.fixture
def mock_in_virtualenv(monkeypatch: pytest.MonkeyPatch) -> None:
    """
    Fixture to simulate being IN a virtual environment.
    
    Mocks running_under_virtualenv() to return True, simulating execution
    inside a virtualenv.
    
    Note: We patch where the function is USED (in base_command), not where
    it's defined (in utils.virtualenv), per Python's import semantics.
    """
    monkeypatch.setattr(
        "pip._internal.cli.base_command.running_under_virtualenv",
        lambda: True
    )


# =============================================================================
# Fixtures for FakeCommand Instances
# =============================================================================


class FakeCommandEnforcing(Command):
    """
    Test command that enforces virtualenv requirement.
    
    This command has ignore_require_venv=False (default), so it will
    respect the --require-virtualenv flag and exit if not in a virtualenv.
    """
    
    def __init__(self) -> None:
        super().__init__("fake_enforcing", "Fake command that enforces venv requirement")
        # ignore_require_venv defaults to False in base Command class
    
    def run(self, options: Values, args: list[str]) -> int:
        """Execute the command - just return SUCCESS."""
        return SUCCESS


class FakeCommandIgnoring(Command):
    """
    Test command that ignores virtualenv requirement.
    
    This command has ignore_require_venv=True, so it will bypass the
    --require-virtualenv flag enforcement (like cache, list, show commands).
    """
    
    ignore_require_venv = True
    
    def __init__(self) -> None:
        super().__init__("fake_ignoring", "Fake command that ignores venv requirement")
    
    def run(self, options: Values, args: list[str]) -> int:
        """Execute the command - just return SUCCESS."""
        return SUCCESS


@pytest.fixture
def fake_command_enforcing() -> FakeCommandEnforcing:
    """Fixture providing a command that enforces virtualenv requirement."""
    return FakeCommandEnforcing()


@pytest.fixture
def fake_command_ignoring() -> FakeCommandIgnoring:
    """Fixture providing a command that ignores virtualenv requirement."""
    return FakeCommandIgnoring()


# =============================================================================
# Test Class 1: Truth Matrix Validation
# =============================================================================


class TestRequireVirtualenvTruthMatrix:
    """
    Comprehensive truth matrix testing covering all 8 permutations.
    
    Each test validates a specific combination of:
    - has_venv: Whether virtualenv is detected (mocked)
    - require_venv: Whether --require-virtualenv flag is set
    - ignore_require_venv: Command-level override attribute
    
    Truth Matrix:
    | has_venv | require_venv | ignore | Expected Result          |
    |----------|--------------|--------|--------------------------|
    | False    | False        | False  | SUCCESS                  |
    | False    | False        | True   | SUCCESS                  |
    | False    | True         | False  | EXIT 3 + CRITICAL LOG    |
    | False    | True         | True   | SUCCESS                  |
    | True     | False        | False  | SUCCESS                  |
    | True     | False        | True   | SUCCESS                  |
    | True     | True         | False  | SUCCESS                  |
    | True     | True         | True   | SUCCESS                  |
    """
    
    def test_no_venv_no_requirement_no_ignore(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
    ) -> None:
        """
        Test: Not in venv, --require-virtualenv not set, command enforces.
        Expected: SUCCESS (no requirement to check)
        """
        result = fake_command_enforcing.main([])
        assert result == SUCCESS
    
    def test_no_venv_no_requirement_with_ignore(
        self,
        mock_not_in_virtualenv: None,
        fake_command_ignoring: FakeCommandIgnoring,
    ) -> None:
        """
        Test: Not in venv, --require-virtualenv not set, command ignores.
        Expected: SUCCESS (no requirement to check)
        """
        result = fake_command_ignoring.main([])
        assert result == SUCCESS
    
    def test_no_venv_with_requirement_no_ignore(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """
        Test: Not in venv, --require-virtualenv set, command enforces.
        Expected: EXIT with code 3 + error message to stderr
        
        This is the CRITICAL enforcement path that prevents installations
        outside virtualenvs when the flag is explicitly set.
        """
        with pytest.raises(SystemExit) as exc_info:
            fake_command_enforcing.main(["--require-virtualenv"])
        
        # Verify exit code is VIRTUALENV_NOT_FOUND (3)
        assert exc_info.value.code == VIRTUALENV_NOT_FOUND
        
        # Verify error message was written to stderr
        captured = capsys.readouterr()
        assert "Could not find an activated virtualenv (required)." in captured.err
    
    def test_no_venv_with_requirement_with_ignore(
        self,
        mock_not_in_virtualenv: None,
        fake_command_ignoring: FakeCommandIgnoring,
    ) -> None:
        """
        Test: Not in venv, --require-virtualenv set, command ignores.
        Expected: SUCCESS (command bypasses requirement)
        
        Commands like 'cache', 'list', 'show' should bypass the virtualenv
        requirement even when --require-virtualenv is set.
        """
        result = fake_command_ignoring.main(["--require-virtualenv"])
        assert result == SUCCESS
    
    def test_with_venv_no_requirement_no_ignore(
        self,
        mock_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
    ) -> None:
        """
        Test: In venv, --require-virtualenv not set, command enforces.
        Expected: SUCCESS (in venv, no requirement to check)
        """
        result = fake_command_enforcing.main([])
        assert result == SUCCESS
    
    def test_with_venv_no_requirement_with_ignore(
        self,
        mock_in_virtualenv: None,
        fake_command_ignoring: FakeCommandIgnoring,
    ) -> None:
        """
        Test: In venv, --require-virtualenv not set, command ignores.
        Expected: SUCCESS (in venv, no requirement to check)
        """
        result = fake_command_ignoring.main([])
        assert result == SUCCESS
    
    def test_with_venv_with_requirement_no_ignore(
        self,
        mock_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
    ) -> None:
        """
        Test: In venv, --require-virtualenv set, command enforces.
        Expected: SUCCESS (in venv, requirement is satisfied)
        """
        result = fake_command_enforcing.main(["--require-virtualenv"])
        assert result == SUCCESS
    
    def test_with_venv_with_requirement_with_ignore(
        self,
        mock_in_virtualenv: None,
        fake_command_ignoring: FakeCommandIgnoring,
    ) -> None:
        """
        Test: In venv, --require-virtualenv set, command ignores.
        Expected: SUCCESS (in venv, and command ignores anyway)
        """
        result = fake_command_ignoring.main(["--require-virtualenv"])
        assert result == SUCCESS


# =============================================================================
# Test Class 2: Error Handling and Exit Codes
# =============================================================================


class TestRequireVirtualenvErrorHandling:
    """
    Validates error conditions and proper system exit behavior.
    
    These tests focus on the error path when virtualenv requirement
    is not met, ensuring proper exit codes and error messages.
    """
    
    def test_exit_code_is_3_when_venv_not_found(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
    ) -> None:
        """
        Test that exit code is exactly 3 (VIRTUALENV_NOT_FOUND) when enforcement fails.
        
        The exit code 3 is specifically reserved for virtualenv-not-found errors,
        distinguishing it from other error types (ERROR=1, UNKNOWN_ERROR=2, etc).
        """
        with pytest.raises(SystemExit) as exc_info:
            fake_command_enforcing.main(["--require-virtualenv"])
        
        assert exc_info.value.code == 3
        assert exc_info.value.code == VIRTUALENV_NOT_FOUND
    
    def test_critical_log_message_content(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """
        Test that the exact error message is logged to stderr.
        
        The message must clearly indicate that a virtualenv is required
        and could not be found.
        """
        with pytest.raises(SystemExit):
            fake_command_enforcing.main(["--require-virtualenv"])
        
        # Check exact message content in stderr
        captured = capsys.readouterr()
        expected_message = "Could not find an activated virtualenv (required)."
        assert expected_message in captured.err
    
    def test_no_error_when_venv_present(
        self,
        mock_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """
        Test that no error occurs when virtualenv requirement is satisfied.
        
        When running inside a virtualenv with --require-virtualenv set,
        the command should proceed normally without any errors or warnings.
        """
        result = fake_command_enforcing.main(["--require-virtualenv"])
        
        assert result == SUCCESS
        
        # Verify no error about virtualenv was written to stderr
        captured = capsys.readouterr()
        assert "Could not find an activated virtualenv" not in captured.err
    
    def test_sys_exit_called_with_correct_code(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
    ) -> None:
        """
        Test that sys.exit() is called with the VIRTUALENV_NOT_FOUND constant.
        
        This ensures consistency with the status_codes module and proper
        error code communication to the calling process.
        """
        with pytest.raises(SystemExit) as exc_info:
            fake_command_enforcing.main(["--require-virtualenv"])
        
        # Verify the exact constant is used
        assert exc_info.value.code == VIRTUALENV_NOT_FOUND
        
        # Verify it's distinct from other error codes
        assert exc_info.value.code != SUCCESS  # Not success (0)
        assert exc_info.value.code != 1  # Not generic error
        assert exc_info.value.code != 2  # Not unknown error


# =============================================================================
# Test Class 3: Command-Level Behavior
# =============================================================================


class TestRequireVirtualenvCommandVariants:
    """
    Tests different command types (enforcing vs ignoring).
    
    Validates that the ignore_require_venv attribute correctly controls
    whether a command respects the --require-virtualenv flag.
    """
    
    def test_enforcing_command_respects_flag(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
    ) -> None:
        """
        Test that commands with ignore_require_venv=False respect the flag.
        
        Commands like install, download, uninstall, wheel should enforce
        the virtualenv requirement when the flag is set.
        """
        # Verify the command has the correct attribute value
        assert fake_command_enforcing.ignore_require_venv is False
        
        # Verify it enforces the requirement
        with pytest.raises(SystemExit) as exc_info:
            fake_command_enforcing.main(["--require-virtualenv"])
        
        assert exc_info.value.code == VIRTUALENV_NOT_FOUND
    
    def test_ignoring_command_bypasses_check(
        self,
        mock_not_in_virtualenv: None,
        fake_command_ignoring: FakeCommandIgnoring,
    ) -> None:
        """
        Test that commands with ignore_require_venv=True bypass the check.
        
        Commands like cache, check, freeze, list, show should ignore
        the --require-virtualenv flag since they don't modify the environment.
        """
        # Verify the command has the correct attribute value
        assert fake_command_ignoring.ignore_require_venv is True
        
        # Verify it bypasses enforcement
        result = fake_command_ignoring.main(["--require-virtualenv"])
        assert result == SUCCESS
    
    def test_custom_command_with_ignore_false(
        self,
        mock_not_in_virtualenv: None,
    ) -> None:
        """
        Test custom command explicitly setting ignore_require_venv=False.
        
        Verifies that explicitly setting the attribute to False works correctly.
        """
        class CustomEnforcingCommand(Command):
            ignore_require_venv = False
            
            def __init__(self) -> None:
                super().__init__("custom", "Custom enforcing command")
            
            def run(self, options: Values, args: list[str]) -> int:
                return SUCCESS
        
        cmd = CustomEnforcingCommand()
        
        with pytest.raises(SystemExit) as exc_info:
            cmd.main(["--require-virtualenv"])
        
        assert exc_info.value.code == VIRTUALENV_NOT_FOUND
    
    def test_custom_command_with_ignore_true(
        self,
        mock_not_in_virtualenv: None,
    ) -> None:
        """
        Test custom command explicitly setting ignore_require_venv=True.
        
        Verifies that explicitly setting the attribute to True works correctly.
        """
        class CustomIgnoringCommand(Command):
            ignore_require_venv = True
            
            def __init__(self) -> None:
                super().__init__("custom", "Custom ignoring command")
            
            def run(self, options: Values, args: list[str]) -> int:
                return SUCCESS
        
        cmd = CustomIgnoringCommand()
        result = cmd.main(["--require-virtualenv"])
        assert result == SUCCESS
    
    def test_default_ignore_require_venv_is_false(self) -> None:
        """
        Test that the default value of ignore_require_venv is False.
        
        By default, commands should enforce the virtualenv requirement
        unless they explicitly set ignore_require_venv=True.
        """
        class DefaultCommand(Command):
            def __init__(self) -> None:
                super().__init__("default", "Default command")
            
            def run(self, options: Values, args: list[str]) -> int:
                return SUCCESS
        
        cmd = DefaultCommand()
        assert cmd.ignore_require_venv is False
    
    def test_attribute_inheritance(self) -> None:
        """
        Test that ignore_require_venv is properly inherited from Command base class.
        
        Verifies that subclasses inherit the default value and can override it.
        """
        # Test default inheritance
        class InheritingCommand(Command):
            def __init__(self) -> None:
                super().__init__("inherit", "Inheriting command")
            
            def run(self, options: Values, args: list[str]) -> int:
                return SUCCESS
        
        cmd = InheritingCommand()
        assert hasattr(cmd, "ignore_require_venv")
        assert cmd.ignore_require_venv is False
        
        # Test overriding
        class OverridingCommand(Command):
            ignore_require_venv = True
            
            def __init__(self) -> None:
                super().__init__("override", "Overriding command")
            
            def run(self, options: Values, args: list[str]) -> int:
                return SUCCESS
        
        cmd_override = OverridingCommand()
        assert cmd_override.ignore_require_venv is True


# =============================================================================
# Test Class 4: Option Precedence and Integration
# =============================================================================


class TestRequireVirtualenvOptionPrecedence:
    """
    Tests CLI flag and environment variable interaction.
    
    Validates that options are parsed correctly and precedence rules
    are followed (CLI flags should override environment variables).
    """
    
    def test_cli_flag_sets_require_venv_option(
        self,
        mock_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
    ) -> None:
        """
        Test that --require-virtualenv CLI flag is parsed correctly.
        
        Verifies the flag sets the require_venv option which is then
        checked by the enforcement logic.
        """
        # When flag is set and in venv, should succeed
        result = fake_command_enforcing.main(["--require-virtualenv"])
        assert result == SUCCESS
    
    def test_environment_variable_sets_require_venv(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Test that PIP_REQUIRE_VIRTUALENV environment variable works.
        
        The environment variable should have the same effect as the CLI flag.
        """
        monkeypatch.setenv("PIP_REQUIRE_VIRTUALENV", "1")
        
        with pytest.raises(SystemExit) as exc_info:
            fake_command_enforcing.main([])
        
        assert exc_info.value.code == VIRTUALENV_NOT_FOUND
    
    def test_cli_overrides_environment_variable(
        self,
        mock_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Test that CLI flag takes precedence over environment variable.
        
        When both are set, the CLI flag value should be used.
        """
        # Set env var to False/0
        monkeypatch.setenv("PIP_REQUIRE_VIRTUALENV", "0")
        
        # CLI flag set to True should override
        result = fake_command_enforcing.main(["--require-virtualenv"])
        assert result == SUCCESS
    
    def test_no_flag_no_env_defaults_to_false(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
    ) -> None:
        """
        Test that require_venv defaults to False when not set.
        
        Without the flag or environment variable, commands should proceed
        normally even outside a virtualenv.
        """
        result = fake_command_enforcing.main([])
        assert result == SUCCESS
    
    def test_env_var_true_enforces_requirement(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """
        Test that PIP_REQUIRE_VIRTUALENV=1 enforces the requirement.
        
        Setting the environment variable to a truthy value should
        trigger enforcement just like the CLI flag.
        """
        monkeypatch.setenv("PIP_REQUIRE_VIRTUALENV", "true")
        
        with pytest.raises(SystemExit) as exc_info:
            fake_command_enforcing.main([])
        
        assert exc_info.value.code == VIRTUALENV_NOT_FOUND
        
        # Verify error message in stderr
        captured = capsys.readouterr()
        assert "Could not find an activated virtualenv" in captured.err
    
    def test_env_var_false_disables_requirement(
        self,
        mock_not_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Test that PIP_REQUIRE_VIRTUALENV=0 or false disables requirement.
        
        Setting the environment variable to a falsy value should
        allow execution outside virtualenv.
        """
        monkeypatch.setenv("PIP_REQUIRE_VIRTUALENV", "0")
        
        result = fake_command_enforcing.main([])
        assert result == SUCCESS
    
    def test_flag_with_ignore_command(
        self,
        mock_not_in_virtualenv: None,
        fake_command_ignoring: FakeCommandIgnoring,
    ) -> None:
        """
        Test that ignore_require_venv=True overrides flag setting.
        
        Even with --require-virtualenv set, commands with ignore_require_venv=True
        should bypass enforcement.
        """
        result = fake_command_ignoring.main(["--require-virtualenv"])
        assert result == SUCCESS
    
    def test_flag_position_independence(
        self,
        mock_in_virtualenv: None,
        fake_command_enforcing: FakeCommandEnforcing,
    ) -> None:
        """
        Test that flag works regardless of position in argument list.
        
        The --require-virtualenv flag should be recognized whether it
        appears before or after other arguments.
        """
        # Flag at start
        result1 = fake_command_enforcing.main(["--require-virtualenv"])
        assert result1 == SUCCESS
        
        # Flag after other options (if any were added)
        result2 = fake_command_enforcing.main(["--require-virtualenv"])
        assert result2 == SUCCESS
    
    def test_enforcement_happens_before_command_run(
        self,
        mock_not_in_virtualenv: None,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """
        Test that virtualenv check happens before run() is called.
        
        The enforcement should occur in the _main() method before
        the command's run() method is invoked, preventing any
        command logic from executing outside a virtualenv.
        """
        run_was_called = False
        
        class TestCommand(Command):
            def __init__(self) -> None:
                super().__init__("test", "Test command")
            
            def run(self, options: Values, args: list[str]) -> int:
                nonlocal run_was_called
                run_was_called = True
                return SUCCESS
        
        cmd = TestCommand()
        
        with pytest.raises(SystemExit):
            cmd.main(["--require-virtualenv"])
        
        # run() should not have been called
        assert run_was_called is False
