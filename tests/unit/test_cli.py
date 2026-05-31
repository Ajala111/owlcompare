"""Acceptance tests for Component 01 (CLI scaffold), per specs/01-cli.md."""

import contextlib
import io
import logging
import sys

from typer.testing import CliRunner

from owlcompare import __version__
from owlcompare.cli import _configure_console_encoding, app, main

runner = CliRunner()


def _combined_output(result) -> str:
    """Return stdout plus stderr, regardless of how the runner split them."""
    text = result.output or ""
    with contextlib.suppress(ValueError):
        # A ValueError means stderr was mixed into stdout; nothing extra to add.
        text += result.stderr or ""
    return text


def test_cli_no_args_shows_help():
    result = runner.invoke(app, [])
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_cli_version_flag_prints_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_version_subcommand_prints_version():
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert __version__ in result.output


def test_cli_version_matches_package_version():
    result = runner.invoke(app, ["version"])
    assert result.output.strip() == f"owlcompare {__version__}"


def test_cli_unknown_command_exits_2():
    result = runner.invoke(app, ["nope"])
    assert result.exit_code == 2
    assert "No such command" in _combined_output(result)


def test_cli_diff_help_lists_options(help_runner, clean):
    result = help_runner.invoke(app, ["diff", "--help"])
    assert result.exit_code == 0
    out = clean(result.output).lower()
    assert "--format" in out
    assert "--out" in out
    assert "ontology_a" in out
    assert "ontology_b" in out


def test_cli_diff_missing_args_exits_2():
    result = runner.invoke(app, ["diff"])
    assert result.exit_code == 2


def test_cli_diff_invalid_format_exits_2():
    result = runner.invoke(app, ["diff", "a.ttl", "b.ttl", "--format", "yaml"])
    assert result.exit_code == 2


def test_cli_diff_stub_exits_2_with_message(capsys, monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    rc = main(["diff", "a.ttl", "b.ttl"])
    assert rc == 2
    assert "Phase 2" in capsys.readouterr().err


def test_cli_verbose_sets_info_level(monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    main(["-v", "version"])
    assert logging.getLogger().level == logging.INFO


def test_cli_double_verbose_sets_debug_level(monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    main(["-vv", "version"])
    assert logging.getLogger().level == logging.DEBUG


def test_cli_quiet_sets_error_level(monkeypatch):
    monkeypatch.delenv("OWLCOMPARE_LOG_LEVEL", raising=False)
    main(["-q", "version"])
    assert logging.getLogger().level == logging.ERROR


def test_cli_log_level_env_overrides_verbose(monkeypatch):
    monkeypatch.setenv("OWLCOMPARE_LOG_LEVEL", "DEBUG")
    main(["-q", "version"])
    assert logging.getLogger().level == logging.DEBUG


def test_main_returns_int():
    rc = main(["--version"])
    assert isinstance(rc, int)
    assert rc == 0


def test_main_reconfigures_stdout_stderr_to_utf8(monkeypatch):
    calls = []

    class FakeStream:
        def reconfigure(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(sys, "stdout", FakeStream())
    monkeypatch.setattr(sys, "stderr", FakeStream())

    _configure_console_encoding()

    assert calls == [
        {"encoding": "utf-8", "errors": "replace"},
        {"encoding": "utf-8", "errors": "replace"},
    ]


def test_main_console_reconfigure_noop_when_stream_lacks_method(monkeypatch):
    # ``io.StringIO`` has no ``reconfigure``; the helper must skip gracefully
    # so the CLI runs cleanly under pytest's captured streams and on platforms
    # where stdout was wrapped by another tool.
    monkeypatch.setattr(sys, "stdout", io.StringIO())
    monkeypatch.setattr(sys, "stderr", io.StringIO())
    _configure_console_encoding()  # must not raise


def test_main_handles_keyboard_interrupt(capsys, monkeypatch):
    def _boom(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr("owlcompare.cli.app", _boom)
    rc = main([])
    assert rc == 130
    assert "Interrupted." in capsys.readouterr().err
