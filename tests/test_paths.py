"""Validation des chemins : traversée, liens symboliques, racine bornée."""

from __future__ import annotations

import os
from pathlib import Path

from mdserve.paths import in_root, safe_bounded, safe_path


def test_chemin_dans_la_racine(tmp_path: Path):
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    assert safe_path(str(root / "sub"), str(root)) == os.path.realpath(root / "sub")


def test_chemin_vide_designe_la_racine(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    assert safe_path("", str(root)) == os.path.realpath(root)


def test_traversee_refusee(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    assert safe_path(str(root / ".." / "etc" / "passwd"), str(root)) is None
    assert safe_path("../etc/passwd", str(root)) is None


def test_lien_symbolique_hors_racine_refuse(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    (root / "lien").symlink_to(dehors, target_is_directory=True)
    assert safe_path(str(root / "lien"), str(root)) is None


def test_nul_refuse(tmp_path: Path):
    root = tmp_path / "root"
    root.mkdir()
    assert safe_path("a\x00b", str(root)) is None


def test_safe_bounded(tmp_path: Path):
    initial = tmp_path / "initial"
    (initial / "a").mkdir(parents=True)
    (initial / "b").mkdir()
    assert safe_bounded(str(initial / "a"), str(initial)) == os.path.realpath(initial / "a")
    # Un sous-dossier frère reste dans le périmètre de départ.
    assert safe_bounded(str(initial / "b"), str(initial)) == os.path.realpath(initial / "b")
    assert safe_bounded(str(tmp_path), str(initial)) is None


def test_in_root(tmp_path: Path):
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    assert in_root(str(root / "sub"), str(root))
    assert in_root(str(root), str(root))
    assert not in_root(str(tmp_path), str(root))
