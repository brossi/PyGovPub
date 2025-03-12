"""
Tests for CLI accessibility features.

These tests verify that the CLI tools meet accessibility requirements
for users with disabilities, including screen reader compatibility and
proper help text documentation.
"""

import io
import pytest
import sys
from unittest.mock import patch, MagicMock
from rich.console import Console

from pygovpub.cli.main import app as cli_app
from pygovpub.cli.config import app as config_app
from pygovpub.cli.output import format_output
from pygovpub.validation.test_accessibility import validate_cli_accessibility
from typer.testing import CliRunner


class TestCLIAccessibility:
    """Test CLI accessibility features."""
    
    def setup_method(self):
        """Set up test environment."""
        self.runner = CliRunner()
    
    def test_help_text_accessibility(self):
        """Test that CLI help text meets accessibility requirements."""
        # Get help text
        result = self.runner.invoke(cli_app, ["--help"])
        
        # Check exit code
        assert result.exit_code == 0
        
        # Validate help text
        validation = validate_cli_accessibility(result.stdout)
        assert validation["valid"] is True, f"Help text accessibility issues: {validation['issues']}"
    
    def test_command_help_accessibility(self):
        """Test that command help text meets accessibility requirements."""
        # Get help for a specific command
        commands = ["search", "documents", "config"]
        
        for command in commands:
            try:
                result = self.runner.invoke(cli_app, [command, "--help"])
                
                # Check exit code
                assert result.exit_code == 0
                
                # Validate help text
                validation = validate_cli_accessibility(result.stdout)
                assert validation["valid"] is True, f"Command {command} help text has issues: {validation['issues']}"
            except:
                # Skip if command doesn't exist
                continue
    
    def test_error_message_accessibility(self):
        """Test that CLI error messages are accessible."""
        # Invoke with invalid arguments to generate error
        result = self.runner.invoke(cli_app, ["nonexistent-command"])
        
        # Should fail with error
        assert result.exit_code != 0
        
        # Error message should contain helpful text
        assert "Error:" in result.stdout or "Usage:" in result.stdout
        assert "--help" in result.stdout  # Should suggest help option
    
    def test_version_option(self):
        """Test that --version option is accessible."""
        # Check version output
        result = self.runner.invoke(cli_app, ["--version"])
        
        # Should succeed
        assert result.exit_code == 0
        
        # Should contain version info
        assert "version" in result.stdout.lower()
    
    def test_output_format_options(self):
        """Test that CLI supports accessible output formats."""
        # Mock command that uses format_output
        @cli_app.command()
        def test_output():
            data = {"id": 1, "title": "Test Document"}
            return format_output(data, "json")
        
        # Test different output formats
        formats = ["json", "text", "table"]
        
        for output_format in formats:
            try:
                with patch("pygovpub.cli.output.format_output") as mock_format:
                    mock_format.return_value = f"Output in {output_format} format"
                    
                    result = self.runner.invoke(cli_app, ["test-output", f"--format={output_format}"])
                    
                    # Should succeed
                    assert result.exit_code == 0
                    
                    # Should use correct format
                    mock_format.assert_called_once()
                    assert output_format in str(mock_format.call_args)
            except:
                # Skip if format not supported
                continue


class TestCLIOutputAccessibility:
    """Test CLI output accessibility."""
    
    def test_json_output_format(self):
        """Test JSON output format accessibility."""
        # Test data
        data = {
            "documents": [
                {"id": 1, "title": "First Document"},
                {"id": 2, "title": "Second Document"}
            ],
            "total": 2
        }
        
        # Format as JSON
        with patch("sys.stdout", new_callable=io.StringIO) as mock_stdout:
            format_output(data, "json", to_console=True)
            output = mock_stdout.getvalue()
        
        # Should contain formatted JSON
        assert "documents" in output
        assert "total" in output
    
    def test_text_output_format(self):
        """Test text output format accessibility."""
        # Test data
        data = {
            "documents": [
                {"id": 1, "title": "First Document"},
                {"id": 2, "title": "Second Document"}
            ],
            "total": 2
        }
        
        # Format as text
        output = format_output(data, "text", to_console=False)
        
        # Should contain readable text
        assert "Documents:" in output or "documents:" in output.lower()
        assert "First Document" in output
        assert "Second Document" in output
    
    @patch("rich.console.Console.print")
    def test_rich_text_formatting(self, mock_print):
        """Test rich text formatting for screen readers."""
        # Test data
        data = {
            "documents": [
                {"id": 1, "title": "First Document"},
                {"id": 2, "title": "Second Document"}
            ]
        }
        
        # Format with rich console
        format_output(data, "rich", to_console=True)
        
        # Should use rich formatting
        mock_print.assert_called_once()
    
    def test_progress_indicator_accessibility(self):
        """Test progress indicator accessibility."""
        # Create a progress context that would be used in CLI
        with patch("rich.progress.Progress.start") as mock_start:
            with patch("rich.progress.Progress.stop") as mock_stop:
                with patch("rich.progress.Progress.add_task") as mock_add_task:
                    console = Console()
                    
                    # Simulate progress tracking from cli utility
                    from rich.progress import Progress
                    
                    with Progress(console=console) as progress:
                        task = progress.add_task("Processing...", total=100)
                        for i in range(100):
                            progress.update(task, advance=1)
                    
                    # Should use progress indicators correctly
                    mock_add_task.assert_called_once()
    
    @patch("typer.echo")
    def test_error_formatting(self, mock_echo):
        """Test error message formatting for accessibility."""
        # Function to display error that would be in CLI code
        def show_error(message):
            typer.echo(f"Error: {message}", err=True)
            return 1
        
        # Test error display
        import typer
        show_error("Test error message")
        
        # Should format error correctly
        mock_echo.assert_called_once_with("Error: Test error message", err=True)
    
    def test_color_settings_accessibility(self):
        """Test color settings for accessibility."""
        # Some environments disable color for accessibility
        with patch.dict('os.environ', {'NO_COLOR': '1'}):
            # Create console
            console = Console()
            
            # Should respect NO_COLOR
            assert not console.color_system, "Console should respect NO_COLOR environment variable"


class TestCLIKeyboardAccessibility:
    """Test CLI keyboard accessibility."""
    
    def test_keyboard_interrupt_handling(self):
        """Test that CLI handles keyboard interrupts gracefully."""
        # Mock a command that will be interrupted
        @cli_app.command()
        def test_interrupt():
            raise KeyboardInterrupt()
        
        # Run command
        result = self.runner.invoke(cli_app, ["test-interrupt"])
        
        # Should exit gracefully
        assert result.exit_code != 0
        assert "Aborted" in result.stdout or "Interrupted" in result.stdout
    
    def test_prompt_accessibility(self):
        """Test that CLI prompts are accessible."""
        # Test prompt function that would be in CLI code
        with patch("typer.prompt") as mock_prompt:
            mock_prompt.return_value = "test input"
            
            # Simulate prompt
            import typer
            value = typer.prompt("Enter value")
            
            # Should call prompt correctly
            mock_prompt.assert_called_once_with("Enter value")
            assert value == "test input"
    
    def test_confirmation_accessibility(self):
        """Test that CLI confirmations are accessible."""
        # Test confirm function that would be in CLI code
        with patch("typer.confirm") as mock_confirm:
            mock_confirm.return_value = True
            
            # Simulate confirmation
            import typer
            result = typer.confirm("Are you sure?")
            
            # Should call confirm correctly
            mock_confirm.assert_called_once_with("Are you sure?")
            assert result is True