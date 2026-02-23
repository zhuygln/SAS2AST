"""CLI integration tests for sas2ast."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


SAS_CODE_DIR = Path(__file__).parent.parent / "sas_code"
COLLAPSE_SAS = SAS_CODE_DIR / "data_step" / "collapse_a_dataset.sas"
DATA_MANIP_SAS = SAS_CODE_DIR / "proc" / "data_manipulation.sas"
RECURSIVE_MACROS_SAS = SAS_CODE_DIR / "macro" / "recursive_macros.sas"


def run_cli(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Run sas2ast CLI and return the result."""
    cmd = [sys.executable, "-m", "sas2ast"] + list(args)
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent.parent),
        check=check,
    )


class TestParseCommand:
    @pytest.mark.skipif(not COLLAPSE_SAS.exists(), reason="Fixture not found")
    def test_parse_tree_default(self):
        result = run_cli("parse", str(COLLAPSE_SAS))
        assert result.returncode == 0
        assert "Program" in result.stdout
        assert "DataStep" in result.stdout or "ProcStep" in result.stdout

    @pytest.mark.skipif(not COLLAPSE_SAS.exists(), reason="Fixture not found")
    def test_parse_tree_explicit(self):
        result = run_cli("parse", str(COLLAPSE_SAS), "--format", "tree")
        assert result.returncode == 0
        assert "Program" in result.stdout

    @pytest.mark.skipif(not COLLAPSE_SAS.exists(), reason="Fixture not found")
    def test_parse_json(self):
        result = run_cli("parse", str(COLLAPSE_SAS), "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "_type" in data
        assert data["_type"] == "ParseResult"

    @pytest.mark.skipif(not COLLAPSE_SAS.exists(), reason="Fixture not found")
    def test_parse_summary(self):
        result = run_cli("parse", str(COLLAPSE_SAS), "--format", "summary")
        assert result.returncode == 0
        assert "Steps:" in result.stdout

    @pytest.mark.skipif(not COLLAPSE_SAS.exists(), reason="Fixture not found")
    def test_parse_html(self):
        result = run_cli("parse", str(COLLAPSE_SAS), "--format", "html")
        assert result.returncode == 0
        assert "<html" in result.stdout

    @pytest.mark.skipif(not COLLAPSE_SAS.exists(), reason="Fixture not found")
    def test_parse_output_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            tmppath = f.name
        try:
            result = run_cli("parse", str(COLLAPSE_SAS), "--output", tmppath)
            assert result.returncode == 0
            content = Path(tmppath).read_text()
            assert "Program" in content
        finally:
            os.unlink(tmppath)


class TestAnalyzeCommand:
    @pytest.mark.skipif(not DATA_MANIP_SAS.exists(), reason="Fixture not found")
    def test_analyze_summary_default(self):
        result = run_cli("analyze", str(DATA_MANIP_SAS))
        assert result.returncode == 0
        assert "Steps:" in result.stdout

    @pytest.mark.skipif(not DATA_MANIP_SAS.exists(), reason="Fixture not found")
    def test_analyze_json(self):
        result = run_cli("analyze", str(DATA_MANIP_SAS), "--format", "json")
        assert result.returncode == 0
        data = json.loads(result.stdout)
        assert "steps" in data

    @pytest.mark.skipif(not DATA_MANIP_SAS.exists(), reason="Fixture not found")
    def test_analyze_tree(self):
        result = run_cli("analyze", str(DATA_MANIP_SAS), "--format", "tree")
        assert result.returncode == 0
        assert "Step Flow" in result.stdout

    @pytest.mark.skipif(not DATA_MANIP_SAS.exists(), reason="Fixture not found")
    def test_analyze_dot(self):
        result = run_cli("analyze", str(DATA_MANIP_SAS), "--format", "dot")
        assert result.returncode == 0
        assert "digraph" in result.stdout

    @pytest.mark.skipif(not DATA_MANIP_SAS.exists(), reason="Fixture not found")
    def test_analyze_html(self):
        result = run_cli("analyze", str(DATA_MANIP_SAS), "--format", "html")
        assert result.returncode == 0
        assert "<html" in result.stdout

    @pytest.mark.skipif(not RECURSIVE_MACROS_SAS.exists(), reason="Fixture not found")
    def test_analyze_macros_summary(self):
        result = run_cli("analyze", str(RECURSIVE_MACROS_SAS), "--format", "summary")
        assert result.returncode == 0
        assert "Macros:" in result.stdout


class TestBatchCommand:
    @pytest.mark.skipif(not SAS_CODE_DIR.exists(), reason="sas_code dir not found")
    def test_batch_summary(self):
        result = run_cli("batch", str(SAS_CODE_DIR), "--format", "summary")
        assert result.returncode == 0
        # Should contain multiple file summaries
        assert result.stdout.count("===") >= 2

    @pytest.mark.skipif(not SAS_CODE_DIR.exists(), reason="sas_code dir not found")
    def test_batch_output_file(self):
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            tmppath = f.name
        try:
            result = run_cli("batch", str(SAS_CODE_DIR), "--output", tmppath)
            assert result.returncode == 0
            content = Path(tmppath).read_text()
            assert len(content) > 0
        finally:
            os.unlink(tmppath)


class TestErrorHandling:
    def test_no_args(self):
        result = run_cli(check=False)
        assert result.returncode == 1

    def test_missing_file(self):
        result = run_cli("parse", "/nonexistent/file.sas", check=False)
        assert result.returncode == 1
        assert "Error" in result.stderr or "error" in result.stderr

    def test_invalid_format(self):
        result = run_cli("parse", str(COLLAPSE_SAS), "--format", "invalid", check=False)
        assert result.returncode != 0

    def test_batch_invalid_dir(self):
        result = run_cli("batch", "/nonexistent/directory", check=False)
        assert result.returncode == 1

    def test_version(self):
        result = run_cli("--version")
        assert result.returncode == 0
        assert "sas2ast" in result.stdout
