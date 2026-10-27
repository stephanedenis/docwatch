"""Routes HTTP, garde-fous et comportement observable du serveur."""

from __future__ import annotations

import json
import os
from pathlib import Path

from conftest import http, http_host


def test_page_accueil(srv):
    statut, entetes, corps = http(srv.base, "/")
    assert statut == 200
    assert entetes["Content-Type"].startswith("text/html")
    assert b"<title>docwatch" in corps
    assert str(srv.root).encode() in corps


def test_arborescence(srv):
    statut, _, corps = http(srv.base, "/tree", path=str(srv.root))
    assert statut == 200
    data = json.loads(corps)
    noms_dirs = {d["name"] for d in data["dirs"]}
    noms_fichiers = {f["name"] for f in data["files"]}
    assert "sub" in noms_dirs
    assert ".cache" not in noms_dirs
    assert "node_modules" not in noms_dirs
    assert "guide.md" in noms_fichiers
    assert ".hidden.md" not in noms_fichiers
    assert isinstance(data["now"], int)


def test_url_propre_document(srv):
    statut, entetes, corps = http(srv.base, "/sub/intro.md")
    assert statut == 200
    assert entetes["Content-Type"].startswith("text/html")
    assert b"docwatch" in corps
    assert b"<title>docwatch" in corps

    statut, _, _ = http(srv.base, "/sub/absent.md")
    assert statut == 404


def test_rendu_markdown_et_annexes(srv):
    statut, _, corps = http(srv.base, "/render", path=str(srv.root / "guide.md"))
    assert statut == 200
    data = json.loads(corps)
    assert "<table>" in data["body"]
    assert "/asset?path=%s" % (srv.root / "img.svg") in data["body"]
    assert 'href="/sub/intro.md"' in data["body"]
    assert data["cache"] is False
    assert data["name"] == "guide.md"
    assert int(data["token"]) > 0


def test_cache_de_rendu(srv):
    url = dict(path=str(srv.root / "guide.md"))
    _, _, c1 = http(srv.base, "/render", **url)
    _, _, c2 = http(srv.base, "/render", **url)
    assert json.loads(c1)["cache"] is False
    assert json.loads(c2)["cache"] is True

    _, _, c3 = http(srv.base, "/render", force="1", **url)
    assert json.loads(c3)["cache"] is False


def test_asset_types(srv):
    for nom, ctype in (
        ("img.svg", "image/svg+xml"),
        ("notes.txt", "text/plain; charset=utf-8"),
        ("sub/pic.png", "image/png"),
    ):
        statut, entetes, corps = http(srv.base, "/asset", path=str(srv.root / nom))
        assert statut == 200, nom
        assert entetes["Content-Type"] == ctype
        assert corps


def test_asset_liste_fermee(srv):
    for nom in ("secret.env", "archive.zip", ".secret.svg"):
        statut, _, _ = http(srv.base, "/asset", path=str(srv.root / nom))
        assert statut == 404, nom


def test_asset_hors_racine(srv):
    statut, _, _ = http(srv.base, "/asset", path="/etc/passwd")
    assert statut == 404


def test_render_hors_racine(srv):
    statut, _, _ = http(srv.base, "/render", path="/etc/passwd")
    assert statut == 404


def test_render_lien_symbolique_hors_racine(srv, tmp_path: Path):
    dehors = tmp_path / "dehors.md"
    dehors.write_text("# dehors", encoding="utf-8")
    (srv.root / "lien.md").symlink_to(dehors)
    statut, _, _ = http(srv.base, "/render", path=str(srv.root / "lien.md"))
    assert statut == 404


def test_epingles_aller_retour(srv):
    sous = str(srv.root / "sub")
    doc = str(srv.root / "guide.md")
    statut, _, corps = http(
        srv.base, "/pins", method="POST", payload={"action": "add", "path": sous, "kind": "folder"}
    )
    assert statut == 200
    assert json.loads(corps)["pins"]["folders"][0]["path"] == sous

    statut, _, _ = http(
        srv.base, "/pins", method="POST", payload={"action": "add", "path": doc, "kind": "file"}
    )
    assert statut == 200
    _, _, corps = http(srv.base, "/pins")
    data = json.loads(corps)
    assert {x["path"] for x in data["pins"]["folders"]} == {sous}
    assert {x["path"] for x in data["pins"]["files"]} == {doc}
    assert data["retires"] == []

    statut, _, _ = http(
        srv.base,
        "/pins",
        method="POST",
        payload={"action": "remove", "path": sous, "kind": "folder"},
    )
    assert statut == 200
    _, _, corps = http(srv.base, "/pins")
    assert json.loads(corps)["pins"]["folders"] == []


def test_epingle_hors_racine_refusee(srv):
    statut, _, _ = http(
        srv.base,
        "/pins",
        method="POST",
        payload={"action": "add", "path": "/etc", "kind": "folder"},
    )
    assert statut == 400


def test_elagage_des_epingles(srv):
    doc = srv.root / "guide.md"
    http(
        srv.base,
        "/pins",
        method="POST",
        payload={"action": "add", "path": str(doc), "kind": "file"},
    )
    doc.unlink()
    _, _, corps = http(srv.base, "/pins", prune="1")
    data = json.loads(corps)
    assert [x["path"] for x in data["retires"]] == [str(doc)]
    assert data["pins"]["files"] == []


def test_changement_de_racine(srv):
    sous = srv.root / "sub"
    statut, _, corps = http(srv.base, "/root", method="POST", payload={"path": str(sous)})
    assert statut == 200
    assert json.loads(corps)["root"] == str(sous)
    _, _, corps = http(srv.base, "/root")
    assert json.loads(corps)["root"] == str(sous)
    assert json.loads(corps)["borne"] == str(srv.root)

    # Remonter au-dessus de la racine de départ est refusé.
    statut, _, _ = http(srv.base, "/root", method="POST", payload={"path": str(srv.root.parent)})
    assert statut == 400


def test_changed(srv):
    doc = srv.root / "guide.md"
    _, _, corps = http(srv.base, "/render", path=str(doc))
    info = json.loads(corps)
    mtime = int(info["mtime"])

    _, _, corps = http(srv.base, "/changed", method="POST", payload={"known": {str(doc): mtime}})
    data = json.loads(corps)
    assert data["changed"] == []
    assert data["missing"] == []

    os.utime(doc, (mtime + 10, mtime + 10))
    _, _, corps = http(srv.base, "/changed", method="POST", payload={"known": {str(doc): mtime}})
    assert json.loads(corps)["changed"][0]["path"] == str(doc)


def test_changed_fichier_absent(srv):
    _, _, corps = http(
        srv.base, "/changed", method="POST", payload={"known": {str(srv.root / "absent.md"): 1}}
    )
    assert json.loads(corps)["missing"] == [str(srv.root / "absent.md")]


def test_stat(srv):
    doc = srv.root / "guide.md"
    _, _, corps = http(srv.base, "/render", path=str(doc))
    info = json.loads(corps)
    _, _, corps = http(
        srv.base, "/stat", path=str(doc), token=info["token"], dir_token=info["dir_token"]
    )
    assert json.loads(corps)["changed"] is False

    mtime = int(info["mtime"]) + 10
    os.utime(doc, (mtime, mtime))
    _, _, corps = http(
        srv.base, "/stat", path=str(doc), token=info["token"], dir_token=info["dir_token"]
    )
    assert json.loads(corps)["changed"] is True


def test_filtre_temporal(srv):
    _, _, corps = http(srv.base, "/recent", heures="1")
    data = json.loads(corps)
    noms = {e["name"] for e in data["elements"]}
    assert "guide.md" in noms
    assert "old.md" not in noms
    assert data["tronque"] is False
    assert data["arbre"]["total"] >= 1


def test_methodes_refusees(srv):
    for methode in ("PUT", "DELETE", "PATCH"):
        statut, _, _ = http(srv.base, "/pins", method=methode)
        assert statut == 405, methode


def test_route_inconnue(srv):
    statut, _, _ = http(srv.base, "/inconnue")
    assert statut == 404


def test_head_sans_corps(srv):
    statut, entetes, corps = http(srv.base, "/", method="HEAD")
    assert statut == 200
    assert corps == b""
    assert int(entetes["Content-Length"]) > 0


def test_hote_non_autorise(srv):
    assert http_host(srv.port, "evil.example") == 403
    assert http_host(srv.port, "127.0.0.1:%d" % srv.port) == 200
    assert http_host(srv.port, "localhost") == 200


def test_origine_non_autorisee(srv):
    payload = {"action": "add", "path": str(srv.root / "sub"), "kind": "folder"}
    statut, _, _ = http(
        srv.base, "/pins", method="POST", payload=payload, headers={"Origin": "http://evil.example"}
    )
    assert statut == 403

    statut, _, _ = http(
        srv.base,
        "/pins",
        method="POST",
        payload=payload,
        headers={"Origin": "http://127.0.0.1:%d" % srv.port},
    )
    assert statut == 200


def test_json_non_objet(srv):
    statut, _, _ = http(srv.base, "/pins", method="POST", payload="pas un objet")
    assert statut == 400
