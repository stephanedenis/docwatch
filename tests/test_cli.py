"""Ligne de commande : options, épingles, erreurs de racine."""

from __future__ import annotations

from pathlib import Path

import pytest

from docwatch.cli import main
from docwatch.docopen import _racine_commune


def test_version(capsys):
    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert "0.3.0" in capsys.readouterr().out


def test_liste_epingles_vide(tmp_path: Path, capsys):
    code = main(["--list-pins", "--config-dir", str(tmp_path / "cfg")])
    assert code == 0
    assert "aucune epingle" in capsys.readouterr().out


def test_epingler_et_lister(tmp_path: Path, capsys):
    root = tmp_path / "docs"
    (root / "sub").mkdir(parents=True)
    (root / "a.md").write_text("# a", encoding="utf-8")
    cfg = str(tmp_path / "cfg")

    code = main([str(root), "--pin", "sub", "--pin-file", "a.md", "--config-dir", cfg])
    assert code == 0
    sortie = capsys.readouterr().out
    assert "epingle (folder)" in sortie
    assert "epingle (file)" in sortie

    assert main(["--list-pins", "--config-dir", cfg]) == 0
    sortie = capsys.readouterr().out
    assert "dossier" in sortie
    assert "document" in sortie


def test_racine_invalide(tmp_path: Path, capsys):
    assert main([str(tmp_path / "absent")]) == 2
    assert "racine invalide" in capsys.readouterr().err


def test_docopen_racine_commune(tmp_path: Path):
    a = tmp_path / "a" / "x.md"
    b = tmp_path / "a" / "sub" / "y.md"
    assert _racine_commune([str(a), str(b)]) == str(tmp_path / "a")
