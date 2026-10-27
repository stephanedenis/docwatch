"""Rendu Markdown, cache et réécriture des annexes."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from docwatch.render import cached_render, freshness, reecrire_assets, render_markdown


def test_table_rendue():
    html = render_markdown("| a | b |\n|---|---|\n| 1 | 2 |\n")
    assert "<table>" in html
    assert "<th>a</th>" in html
    assert "<td>1</td>" in html


def test_image_relative_reecrite(docs: Path):
    html = reecrire_assets('<p><img src="img.svg" alt="x"></p>', str(docs), str(docs))
    assert "/asset?path=%s" % (docs / "img.svg") in html


def test_image_dans_sous_dossier(monkeypatch, docs: Path):
    html = reecrire_assets('<img src="pic.png">', str(docs / "sub"), str(docs))
    assert "/asset?path=%s" % (docs / "sub" / "pic.png") in html


def test_image_absolue_resolue_contre_la_racine(docs: Path):
    html = reecrire_assets('<img src="/img.svg">', str(docs / "sub"), str(docs))
    assert "/asset?path=%s" % (docs / "img.svg") in html


def test_lien_markdown_ouvre_le_lecteur(docs: Path):
    html = reecrire_assets('<a href="sub/intro.md">Intro</a>', str(docs), str(docs))
    assert "/?f=%s" % (docs / "sub" / "intro.md") in html
    assert 'href="sub/intro.md"' not in html


def test_lien_markdown_absolu(docs: Path):
    html = reecrire_assets('<a href="/sub/intro.md">Intro</a>', str(docs), str(docs))
    assert "/?f=%s" % (docs / "sub" / "intro.md") in html


def test_lien_markdown_avec_fragment(docs: Path):
    html = reecrire_assets('<a href="sub/intro.md#partie">Intro</a>', str(docs), str(docs))
    assert "/?f=%s#partie" % (docs / "sub" / "intro.md") in html


def test_url_externe_ancre_et_schema_inchanges(docs: Path):
    attendu = (
        '<a href="https://example.com">x</a>'
        '<a href="#ancre">y</a>'
        '<a href="mailto:a@b.c">z</a>'
        '<img src="data:image/png;base64,AAA">'
    )
    assert reecrire_assets(attendu, str(docs), str(docs)) == attendu


def test_sortie_de_racine_inchangee(docs: Path):
    attendu = '<img src="../../etc/passwd">'
    assert reecrire_assets(attendu, str(docs), str(docs)) == attendu


def test_type_non_autorise_inchange(docs: Path):
    attendu = '<a href="secret.env">secret</a>'
    assert reecrire_assets(attendu, str(docs), str(docs)) == attendu


def test_attribut_pas_en_premier(docs: Path):
    html = reecrire_assets('<img alt="x" src="img.svg" width="10">', str(docs), str(docs))
    assert "/asset?path=%s" % (docs / "img.svg") in html
    assert 'alt="x"' in html
    assert 'width="10"' in html


def test_cache_rendu(docs: Path, tmp_path: Path):
    cache = tmp_path / "cache"
    body1, hit1 = cached_render(str(docs / "guide.md"), str(cache))
    body2, hit2 = cached_render(str(docs / "guide.md"), str(cache))
    assert body1 == body2
    assert hit1 is False
    assert hit2 is True

    time.sleep(0.01)
    with open(docs / "guide.md", "a", encoding="utf-8") as f:
        f.write("\n\nSuite.\n")
    body3, hit3 = cached_render(str(docs / "guide.md"), str(cache))
    assert hit3 is False
    assert body3 != body1


def test_freshness(docs: Path):
    p = str(docs / "guide.md")
    assert freshness(p, 0, 0)["changed"] is False
    vieux = os.stat(p).st_mtime_ns - 1
    info = freshness(p, vieux, 0)
    assert info["exists"] is True
    assert info["changed"] is True


def test_freshness_fichier_absent(docs: Path):
    assert freshness(str(docs / "absent.md"), 1, 1) == {"exists": False}


@pytest.mark.parametrize("texte", ["", "pas de markdown"])
def test_rendu_ne_leve_pas(texte):
    assert isinstance(render_markdown(texte), str)
