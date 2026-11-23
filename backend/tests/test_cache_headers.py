"""Static files: hashed build files are cached for a year; everything else is re-checked with the
server, so a replaced image shows at once instead of after a browser's heuristic expiry."""
from starlette.applications import Starlette
from starlette.testclient import TestClient

from app.main import IMMUTABLE, REVALIDATE, CachedStaticFiles


def _client(tmp_path):
    (tmp_path / "img").mkdir()
    (tmp_path / "img" / "twin-room.jpg").write_bytes(b"\xff\xd8photo")
    (tmp_path / "index-DZINiWYW.js").write_text("console.log(1)")
    (tmp_path / "index-YouG4Lmv.css").write_text("body{}")
    app = Starlette()
    app.mount("/assets", CachedStaticFiles(directory=tmp_path))
    return TestClient(app)


def test_images_are_revalidated(tmp_path):
    r = _client(tmp_path).get("/assets/img/twin-room.jpg")
    assert r.status_code == 200
    assert r.headers["cache-control"] == REVALIDATE == "no-cache"
    assert r.headers.get("etag")


def test_unchanged_image_answers_304(tmp_path):
    c = _client(tmp_path)
    etag = c.get("/assets/img/twin-room.jpg").headers["etag"]
    r = c.get("/assets/img/twin-room.jpg", headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert r.headers["cache-control"] == REVALIDATE


def test_hashed_build_files_are_immutable(tmp_path):
    c = _client(tmp_path)
    for path in ("/assets/index-DZINiWYW.js", "/assets/index-YouG4Lmv.css"):
        r = c.get(path)
        assert r.status_code == 200
        assert r.headers["cache-control"] == IMMUTABLE
