"""Configuration : racine, répertoires explicites, racines XDG."""

from __future__ import annotations

from pathlib import Path

import pytest

from docwatch.config import make_settings


def test_repertoires_explicites_utilises_tels_quels(tmp_path: Path):
    settings = make_settings(
        root=str(tmp_path),
        config_dir=str(tmp_path / "cfg"),
        cache_dir=str(tmp_path / "cache"),
    )
    assert settings.config_dir == str(tmp_path / "cfg")
    assert settings.pins_file == str(tmp_path / "cfg" / "pins.json")
    assert settings.cache_dir == str(tmp_path / "cache")


def test_racines_xdg(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg-config"))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "xdg-cache"))
    settings = make_settings(root=str(tmp_path))
    assert settings.config_dir == str(tmp_path / "xdg-config" / "docwatch")
    assert settings.cache_dir == str(tmp_path / "xdg-cache" / "docwatch")


def test_racine_invalide(tmp_path: Path):
    with pytest.raises(ValueError):
        make_settings(root=str(tmp_path / "absent"))


def test_port_invalide(tmp_path: Path):
    with pytest.raises(ValueError):
        make_settings(root=str(tmp_path), port=70000)
