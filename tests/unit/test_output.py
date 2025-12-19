"""Tests for the output module."""


class TestVerboseOutput:
    """Tests for verbose output functionality."""

    def setup_method(self):
        """Reset verbose state before each test."""
        from ha_tools.lib.output import set_verbose

        set_verbose(False)

    def teardown_method(self):
        """Reset verbose state after each test."""
        from ha_tools.lib.output import set_verbose

        set_verbose(False)

    def test_verbose_disabled_by_default(self):
        """Test that verbose is disabled by default."""
        from ha_tools.lib.output import is_verbose

        assert not is_verbose()

    def test_set_verbose_enables(self):
        """Test enabling verbose mode."""
        from ha_tools.lib.output import is_verbose, set_verbose

        set_verbose(True)
        assert is_verbose()

    def test_set_verbose_disables(self):
        """Test disabling verbose mode."""
        from ha_tools.lib.output import is_verbose, set_verbose

        set_verbose(True)
        assert is_verbose()
        set_verbose(False)
        assert not is_verbose()

    def test_print_verbose_when_enabled(self, capsys):
        """Test that print_verbose outputs when verbose is enabled."""
        from ha_tools.lib.output import print_verbose, set_verbose

        set_verbose(True)
        print_verbose("test message")
        # Rich outputs to stderr by default
        captured = capsys.readouterr()
        # The output should contain the message (wrapped in dim styling)
        assert "test message" in captured.out or "test message" in captured.err

    def test_print_verbose_when_disabled(self, capsys):
        """Test that print_verbose does not output when verbose is disabled."""
        from ha_tools.lib.output import print_verbose, set_verbose

        set_verbose(False)
        print_verbose("test message")
        captured = capsys.readouterr()
        # Should not output anything
        assert "test message" not in captured.out
        assert "test message" not in captured.err

    def test_print_verbose_timing_when_enabled(self, capsys):
        """Test that print_verbose_timing outputs when verbose is enabled."""
        from ha_tools.lib.output import print_verbose_timing, set_verbose

        set_verbose(True)
        print_verbose_timing("Test operation", 123.4)
        captured = capsys.readouterr()
        # Should contain both the operation name and timing
        output = captured.out + captured.err
        assert "Test operation" in output
        assert "123.4ms" in output

    def test_print_verbose_timing_when_disabled(self, capsys):
        """Test that print_verbose_timing does not output when verbose is disabled."""
        from ha_tools.lib.output import print_verbose_timing, set_verbose

        set_verbose(False)
        print_verbose_timing("Test operation", 123.4)
        captured = capsys.readouterr()
        # Should not output anything
        assert "Test operation" not in captured.out
        assert "Test operation" not in captured.err
