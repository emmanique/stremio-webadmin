"""Regression tests for the bundled Stremio Web Continue Watching patch."""
from __future__ import annotations

import importlib.util
from pathlib import Path

_PATH = Path(__file__).resolve().parents[1] / "docker" / "patch_continue_watching.py"
_SPEC = importlib.util.spec_from_file_location("patch_continue_watching", _PATH)
_MOD = importlib.util.module_from_spec(_SPEC)
assert _SPEC.loader is not None
_SPEC.loader.exec_module(_MOD)


def test_patch_only_targets_centre_play_inside_continue_watching():
    source = 'x=e?"string"==typeof e.metaDetailsStreams?e.metaDetailsStreams:"string"==typeof e.player?e.player:null:null;'
    patched, status = _MOD.patch_text(source)
    assert status == 1
    assert patched.startswith(source)
    assert patched.count(source) == 1
    assert _MOD.MARKER in patched
    assert 'play-icon-layer' in patched
    assert 'poster-change-cursor' in patched
    assert 'e.selectPrevented=true' in patched
    assert 'preventDefault' not in patched
    assert 'stopImmediatePropagation' not in patched
    assert 'dispatchEvent' not in patched


def test_patch_leaves_poster_and_details_navigation_alone():
    patched, status = _MOD.patch_text("bundle;")
    assert status == 1
    assert 'const play=t.closest(\'[class*="play-icon-layer"]\');if(!play)return;' in patched
    assert 'const poster=play.closest(\'[class*="poster-change-cursor"]\');if(!poster)return;' in patched


def test_patch_is_idempotent():
    once, status = _MOD.patch_text("bundle;")
    assert status == 1
    twice, status = _MOD.patch_text(once)
    assert status == 0
    assert twice == once
