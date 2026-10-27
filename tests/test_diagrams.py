"""Génération PlantUML/Mermaid : blocs, fichiers sources, affixe, cache."""

from __future__ import annotations

import re
import stat
from pathlib import Path

import pytest

from conftest import http
from docwatch import diagrams
from docwatch.config import DiagramSettings


def _outil_plantuml(tmp_path: Path) -> Path:
    script = tmp_path / "faux-plantuml"
    script.write_text(
        "#!/bin/sh\ncat >/dev/null\nprintf '%s' '<svg width=\"10\" height=\"20\"><rect/></svg>'\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


def _outil_mermaid(tmp_path: Path) -> Path:
    script = tmp_path / "faux-mermaid"
    script.write_text(
        "#!/usr/bin/env python3\n"
        "import pathlib, sys\n"
        "a = sys.argv[1:]\n"
        "out = pathlib.Path(a[a.index('-o') + 1])\n"
        "out.write_text('<svg viewBox=\"0 0 5 5\"><circle/></svg>', encoding='utf-8')\n",
        encoding="utf-8",
    )
    script.chmod(script.stat().st_mode | stat.S_IXUSR)
    return script


@pytest.fixture
def outils(tmp_path: Path) -> DiagramSettings:
    return DiagramSettings(
        enabled=True,
        plantuml=str(_outil_plantuml(tmp_path)),
        mermaid=str(_outil_mermaid(tmp_path)),
        timeout=10,
    )


def test_bloc_puml_genere_et_placeholder(outils: DiagramSettings, tmp_path: Path):
    cache = tmp_path / "cache"
    texte = "# A\n\n```puml\nAlice -> Bob: test\n```\n"
    prepare = diagrams.preparer_texte(texte, str(cache), outils)
    m = re.search(r"<!--diagram:([0-9a-f]+)\.puml-->", prepare)
    assert m, prepare
    h = m.group(1)
    fichier = cache / "diagrams" / ("%s.puml.svg" % h)
    assert fichier.is_file()
    svg = fichier.read_text(encoding="utf-8")
    assert "viewBox=" in svg
    assert "<title>Diagramme PlantUML</title>" in svg
    assert "<desc>Généré par PlantUML</desc>" in svg
    rendu = diagrams.remplacer_placeholders(prepare)
    assert 'src="/diagram/%s.puml.svg"' % h in rendu


def test_bloc_mermaid_genere(outils: DiagramSettings, tmp_path: Path):
    cache = tmp_path / "cache"
    texte = "```mmd\ngraph TD; A-->B;\n```\n"
    prepare = diagrams.preparer_texte(texte, str(cache), outils)
    m = re.search(r"<!--diagram:([0-9a-f]+)\.mmd-->", prepare)
    assert m
    assert (cache / "diagrams" / ("%s.mmd.svg" % m.group(1))).is_file()


def test_fichiers_sources_preservent_affixe(outils: DiagramSettings, tmp_path: Path):
    puml = tmp_path / "diagramme.puml"
    puml.write_text("@startuml\nA -> B\n@enduml\n", encoding="utf-8")
    mmd = tmp_path / "diagramme.mmd"
    mmd.write_text("graph TD; A-->B;\n", encoding="utf-8")

    sortie_p = diagrams.generer_fichier_source(str(puml), outils)
    sortie_m = diagrams.generer_fichier_source(str(mmd), outils)
    assert sortie_p == tmp_path / "diagramme.puml.svg"
    assert sortie_m == tmp_path / "diagramme.mmd.svg"
    assert sortie_p.is_file() and sortie_m.is_file()
    assert "docwatch-generated" in sortie_p.read_text(encoding="utf-8")
    # Une deuxième passe ne réécrit pas un SVG plus récent que sa source.
    avant = sortie_p.stat().st_mtime_ns
    assert diagrams.generer_fichier_source(str(puml), outils) == sortie_p
    assert sortie_p.stat().st_mtime_ns == avant


def test_outil_absent_laisse_le_bloc(tmp_path: Path):
    reglages = DiagramSettings(
        enabled=True,
        plantuml=str(tmp_path / "absent-plantuml"),
        mermaid=str(tmp_path / "absent-mermaid"),
    )
    texte = "```puml\nA -> B\n```\n"
    assert diagrams.preparer_texte(texte, str(tmp_path / "cache"), reglages) == texte


def test_reecriture_assets_laisse_les_diagrammes(docs: Path):
    from docwatch.render import reecrire_assets

    attendu = '<img src="/diagram/0123456789abcdef01234567.puml.svg">'
    assert reecrire_assets(attendu, str(docs), str(docs)) == attendu


def test_route_diagramme(srv):
    cache = Path(srv.state.settings.cache_dir) / "diagrams"
    cache.mkdir(parents=True, exist_ok=True)
    h = "0123456789abcdef01234567"
    (cache / ("%s.puml.svg" % h)).write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1">'
        "<title>x</title><desc>y</desc></svg>",
        encoding="utf-8",
    )
    statut, entetes, corps = http(srv.base, "/diagram/%s.puml.svg" % h)
    assert statut == 200
    assert entetes["Content-Type"] == "image/svg+xml"
    assert b"<svg" in corps
    statut, _, _ = http(srv.base, "/diagram/absent.puml.svg")
    assert statut == 404
