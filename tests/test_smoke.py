"""Smoke tests -- run the full pipeline and verify it doesn't crash."""

import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DEMO = ROOT / 'demo'
BUILD = DEMO / 'build'
PYTHON = sys.executable


@pytest.fixture(autouse=True)
def clean_build():
    """Wipe build/ before each test so results are deterministic."""
    if BUILD.exists():
        shutil.rmtree(BUILD)
    yield
    # leave build/ for inspection on failure


def run_torrenzo(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [PYTHON, '-m', 'torrenzo', str(DEMO), *args],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )


class TestBuild:
    def test_full_build(self):
        result = run_torrenzo('--force')
        assert result.returncode == 0, result.stderr
        assert '10 file(s) newly built' in result.stdout

    def test_expected_outputs_exist(self):
        run_torrenzo('--force')
        assert (BUILD / 'assessments_briefs' / 'assessment_01.pdf').exists()
        assert (BUILD / 'modules_html' / 'mod_00_01_welcome.html').exists()
        assert (BUILD / 'modules_html' / 'mod_01_01_introduction.html').exists()
        assert (BUILD / 'modules_html' / 'mod_01_03_lemons.html').exists()
        assert (BUILD / 'lecturer_notes' / 'SUBJECT_NOTES.md').exists()

    def test_incremental_skips(self):
        run_torrenzo('--force')
        result = run_torrenzo()
        assert result.returncode == 0
        assert 'up-to-date, skipped' in result.stdout
        assert 'newly built' not in result.stdout

    def test_clean_rebuilds_all(self):
        run_torrenzo('--force')
        result = run_torrenzo('--clean')
        assert result.returncode == 0
        assert '10 file(s) newly built' in result.stdout


class TestCC:
    def test_cc_export(self):
        result = run_torrenzo('--force', '--cc')
        assert result.returncode == 0, result.stderr
        assert 'Common Cartridge' in result.stdout

    def test_imscc_is_valid_zip(self):
        import zipfile
        run_torrenzo('--force', '--cc')
        imscc = BUILD / 'FRU101.imscc'
        assert imscc.exists()
        with zipfile.ZipFile(imscc) as zf:
            names = zf.namelist()
            assert 'imsmanifest.xml' in names


class TestTags:
    def test_build_tag_map(self):
        from torrenzo.torrenzo_engine.tags import build_tag_map
        tags = build_tag_map(DEMO)
        assert 'outline.subject.code' in tags
        assert tags['outline.subject.code'] == 'FRU101'
        assert 'slo' in tags
        assert 'assessment|a1|meta_table' in tags

    def test_load_outline(self):
        from torrenzo.torrenzo_engine.tags import load_outline
        data = load_outline(DEMO)
        assert data['subject']['code'] == 'FRU101'
        assert 'slo' in data
        assert 'assessment' in data
