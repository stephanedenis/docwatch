"""Épingles : formats, ajout/retrait, élagage, permissions."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path

from mdserve.pins import (
    load_pins,
    pin_entry,
    pins_action,
    pins_for_root,
    pins_with_mtime,
    prune_pins,
    save_pins,
)


def test_ajout_et_retrait(tmp_path: Path):
    fichier = tmp_path / "config" / "pins.json"
    dossier = tmp_path / "docs"
    dossier.mkdir()
    doc = dossier / "a.md"
    doc.write_text("# a", encoding="utf-8")

    pins_action("add", str(dossier), "folder", str(fichier))
    pins_action("add", str(doc), "file", str(fichier))
    pins = load_pins(str(fichier))
    assert [x["path"] for x in pins["folders"]] == [str(dossier)]
    assert [x["path"] for x in pins["files"]] == [str(doc)]

    pins_action("remove", str(dossier), "folder", str(fichier))
    pins = load_pins(str(fichier))
    assert pins["folders"] == []
    assert pins["files"] == []  # le document enfant part avec le dossier


def test_toggle(tmp_path: Path):
    fichier = tmp_path / "pins.json"
    dossier = tmp_path / "docs"
    dossier.mkdir()
    pins_action("toggle", str(dossier), "folder", str(fichier))
    assert len(load_pins(str(fichier))["folders"]) == 1
    pins_action("toggle", str(dossier), "folder", str(fichier))
    assert load_pins(str(fichier))["folders"] == []


def test_ancien_format_converti(tmp_path: Path):
    dossier = tmp_path / "docs"
    dossier.mkdir()
    doc = dossier / "a.md"
    doc.write_text("# a", encoding="utf-8")
    fichier = tmp_path / "pins.json"
    fichier.write_text(json.dumps([str(dossier), str(doc)]), encoding="utf-8")
    pins = load_pins(str(fichier))
    assert [x["path"] for x in pins["folders"]] == [str(dossier)]
    assert [x["path"] for x in pins["files"]] == [str(doc)]


def test_entree_invalide_ignoree(tmp_path: Path):
    fichier = tmp_path / "pins.json"
    fichier.write_text(json.dumps({"folders": [None, {}, "x"]}), encoding="utf-8")
    # "x" est un chemin relatif : conservé comme dossier, mais sans casser la lecture.
    pins = load_pins(str(fichier))
    assert all("path" in x for x in pins["folders"])


def test_permissions_du_fichier(tmp_path: Path):
    fichier = tmp_path / "config" / "pins.json"
    save_pins({"folders": [], "files": []}, str(fichier))
    mode = stat.S_IMODE(os.stat(fichier).st_mode)
    assert mode == 0o600


def test_pins_for_root(tmp_path: Path):
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    dehors = tmp_path / "dehors"
    dehors.mkdir()
    pins = {"folders": [pin_entry(str(root / "sub")), pin_entry(str(dehors))], "files": []}
    visibles = pins_for_root(pins, str(root))
    assert [x["path"] for x in visibles["folders"]] == [str(root / "sub")]


def test_pins_with_mtime(tmp_path: Path):
    dossier = tmp_path / "docs"
    dossier.mkdir()
    doc = dossier / "a.md"
    doc.write_text("# a", encoding="utf-8")
    enrichi = pins_with_mtime(
        {"folders": [pin_entry(str(dossier))], "files": [pin_entry(str(doc))]}
    )
    assert enrichi["folders"][0]["kind"] == "folder"
    assert enrichi["files"][0]["kind"] == "file"
    assert enrichi["files"][0]["existe"] is True


def test_elagage_document(tmp_path: Path):
    root = tmp_path / "root"
    (root / "sub").mkdir(parents=True)
    doc = root / "sub" / "a.md"
    doc.write_text("# a", encoding="utf-8")
    fichier = tmp_path / "pins.json"
    pins_action("add", str(doc), "file", str(fichier))

    doc.unlink()
    retires = prune_pins(str(fichier), str(root))
    assert [x["path"] for x in retires] == [str(doc)]
    assert load_pins(str(fichier))["files"] == []


def test_elagage_conserve_si_le_parent_disparait(tmp_path: Path):
    root = tmp_path / "root"
    (root / "a" / "b").mkdir(parents=True)
    doc = root / "a" / "b" / "x.md"
    doc.write_text("# x", encoding="utf-8")
    fichier = tmp_path / "pins.json"
    pins_action("add", str(doc), "file", str(fichier))

    # Tout le sous-arbre a/ disparaît : le dossier parent immédiat n'existe
    # plus, on conserve l'épingle (support débranché, dossier déplacé).
    for p in sorted((root / "a").rglob("*"), key=lambda x: len(x.parts), reverse=True):
        if p.is_file():
            p.unlink()
        else:
            p.rmdir()
    (root / "a").rmdir()
    retires = prune_pins(str(fichier), str(root))
    assert retires == []
    assert len(load_pins(str(fichier))["files"]) == 1
