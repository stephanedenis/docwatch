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


def _ecrire_config(tmp_path: Path, mounts, port=9999, diagrams=None):
    lignes = ["[server]", "port = %d" % port, ""]
    for nom, chemin, label in mounts:
        lignes += [
            "[[mounts]]",
            'name = "%s"' % nom,
            'path = "%s"' % chemin,
            'label = "%s"' % label,
            "",
        ]
    if diagrams:
        lignes.append("[diagrams]")
        for cle, valeur in diagrams.items():
            if isinstance(valeur, str):
                lignes.append('%s = "%s"' % (cle, valeur))
            else:
                lignes.append("%s = %s" % (cle, str(valeur).lower()))
    chemin = tmp_path / "config.toml"
    chemin.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    return chemin


def test_config_multi_mounts(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    config = _ecrire_config(
        tmp_path,
        [("premier", str(a), "Premier"), ("second", str(b), "Second")],
        diagrams={"enabled": False, "plantuml": "/opt/plantuml"},
    )
    settings = make_settings(
        config_path=str(config),
        config_dir=str(tmp_path / "cfg"),
        cache_dir=str(tmp_path / "cache"),
    )
    assert [m.name for m in settings.mounts] == ["premier", "second"]
    assert settings.mounts[0].path == str(a)
    assert settings.root == str(a)
    assert settings.port == 9999
    assert settings.diagrams.enabled is False
    assert settings.diagrams.plantuml == "/opt/plantuml"


def test_config_port_ecrase_par_cli(tmp_path: Path):
    a = tmp_path / "a"
    a.mkdir()
    config = _ecrire_config(tmp_path, [("a", str(a), "A")], port=9999)
    settings = make_settings(
        config_path=str(config),
        port=8777,
        config_dir=str(tmp_path / "cfg"),
        cache_dir=str(tmp_path / "cache"),
    )
    assert settings.port == 8777


def test_config_nom_en_double(tmp_path: Path):
    a = tmp_path / "a"
    b = tmp_path / "b"
    a.mkdir()
    b.mkdir()
    config = _ecrire_config(tmp_path, [("meme", str(a), "A"), ("meme", str(b), "B")])
    with pytest.raises(ValueError):
        make_settings(
            config_path=str(config),
            config_dir=str(tmp_path / "cfg"),
            cache_dir=str(tmp_path / "cache"),
        )


def test_config_racine_absente(tmp_path: Path):
    config = _ecrire_config(tmp_path, [("absent", str(tmp_path / "absent"), "Absent")])
    with pytest.raises(ValueError):
        make_settings(
            config_path=str(config),
            config_dir=str(tmp_path / "cfg"),
            cache_dir=str(tmp_path / "cache"),
        )


def test_racine_et_config_exclusifs(tmp_path: Path):
    a = tmp_path / "a"
    a.mkdir()
    config = _ecrire_config(tmp_path, [("a", str(a), "A")])
    with pytest.raises(ValueError):
        make_settings(
            root=str(a),
            config_path=str(config),
            config_dir=str(tmp_path / "cfg"),
            cache_dir=str(tmp_path / "cache"),
        )
