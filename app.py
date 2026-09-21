"""Generador local de QRs dinámicos.

Cada QR codifica una URL fija (BASE_URL/r/<slug>) que redirige al destino
real. Cambiar el destino no requiere reimprimir el QR.
"""
import io
import json
import re
import sqlite3
from datetime import datetime
from functools import wraps
from pathlib import Path

import qrcode
import qrcode.image.svg
from flask import (Flask, abort, flash, g, redirect, render_template, request,
                   send_file, url_for)

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
DB_PATH = DATA_DIR / "qr.db"
CONFIG_PATH = DATA_DIR / "config.json"
EXPORT_DIR = ROOT / "docs"  # carpeta que GitHub Pages sirve por defecto

DEFAULT_CONFIG = {"base_url": "http://127.0.0.1:5000", "mode": "server"}
SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")

app = Flask(__name__)
app.secret_key = "qr-generator-local"


# ---------- config / db ----------

def load_config():
    if CONFIG_PATH.exists():
        return {**DEFAULT_CONFIG, **json.loads(CONFIG_PATH.read_text(encoding="utf-8"))}
    return dict(DEFAULT_CONFIG)


def save_config(cfg):
    DATA_DIR.mkdir(exist_ok=True)
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def get_db():
    if "db" not in g:
        DATA_DIR.mkdir(exist_ok=True)
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("""
            CREATE TABLE IF NOT EXISTS codes (
                slug TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                target TEXT NOT NULL,
                scans INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )""")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def public_url(slug, cfg=None):
    cfg = cfg or load_config()
    base = cfg["base_url"].rstrip("/")
    # En modo estático GitHub Pages sirve /r/<slug>/index.html
    return f"{base}/r/{slug}/" if cfg["mode"] == "static" else f"{base}/r/{slug}"


def normalize_target(url):
    url = url.strip()
    if url and not re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", url):
        url = "https://" + url
    return url


# ---------- guard: el panel solo es accesible desde este PC ----------

def local_only(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        proxied = any(h in request.headers for h in
                      ("X-Forwarded-For", "Cf-Connecting-Ip", "X-Real-Ip"))
        if request.remote_addr not in ("127.0.0.1", "::1") or proxied:
            abort(404)
        return view(*args, **kwargs)
    return wrapper


# ---------- panel ----------

@app.route("/")
@local_only
def index():
    codes = get_db().execute("SELECT * FROM codes ORDER BY updated_at DESC").fetchall()
    cfg = load_config()
    return render_template("index.html", codes=codes, cfg=cfg,
                           public_url=lambda s: public_url(s, cfg))


@app.post("/create")
@local_only
def create():
    slug = request.form.get("slug", "").strip().lower()
    name = request.form.get("name", "").strip() or slug
    target = normalize_target(request.form.get("target", ""))
    if not SLUG_RE.match(slug):
        flash("Slug inválido: usa minúsculas, números y guiones.", "error")
    elif not target:
        flash("Falta la URL de destino.", "error")
    else:
        now = datetime.now().isoformat(timespec="seconds")
        try:
            db = get_db()
            db.execute("INSERT INTO codes (slug, name, target, created_at, updated_at) "
                       "VALUES (?, ?, ?, ?, ?)", (slug, name, target, now, now))
            db.commit()
            flash(f"QR '{slug}' creado.", "ok")
        except sqlite3.IntegrityError:
            flash(f"Ya existe un QR con slug '{slug}'.", "error")
    return redirect(url_for("index"))


@app.post("/code/<slug>/update")
@local_only
def update(slug):
    name = request.form.get("name", "").strip() or slug
    target = normalize_target(request.form.get("target", ""))
    if not target:
        flash("La URL de destino no puede estar vacía.", "error")
        return redirect(url_for("index"))
    db = get_db()
    db.execute("UPDATE codes SET name=?, target=?, updated_at=? WHERE slug=?",
               (name, target, datetime.now().isoformat(timespec="seconds"), slug))
    db.commit()
    msg = f"Destino de '{slug}' actualizado."
    if load_config()["mode"] == "static":
        msg += " Recuerda exportar y publicar para que se aplique."
    flash(msg, "ok")
    return redirect(url_for("index"))


@app.post("/code/<slug>/delete")
@local_only
def delete(slug):
    db = get_db()
    db.execute("DELETE FROM codes WHERE slug=?", (slug,))
    db.commit()
    flash(f"QR '{slug}' eliminado.", "ok")
    return redirect(url_for("index"))


@app.post("/settings")
@local_only
def settings():
    base = request.form.get("base_url", "").strip().rstrip("/")
    mode = request.form.get("mode", "server")
    if not re.match(r"^https?://", base):
        flash("La URL base debe empezar por http:// o https://", "error")
    else:
        save_config({"base_url": base, "mode": mode if mode in ("server", "static") else "server"})
        flash("Configuración guardada. Ojo: los QR ya impresos siguen apuntando a la URL base anterior.", "ok")
    return redirect(url_for("index"))


@app.post("/export")
@local_only
def export():
    n = export_static()
    flash(f"Exportados {n} redirects en /docs. Haz commit + push para publicarlos.", "ok")
    return redirect(url_for("index"))


@app.route("/qr/<slug>.<fmt>")
@local_only
def qr_image(slug, fmt):
    if fmt not in ("png", "svg"):
        abort(404)
    if not get_db().execute("SELECT 1 FROM codes WHERE slug=?", (slug,)).fetchone():
        abort(404)
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=int(request.args.get("size", 12)), border=4)
    qr.add_data(public_url(slug))
    qr.make(fit=True)
    buf = io.BytesIO()
    if fmt == "svg":
        qr.make_image(image_factory=qrcode.image.svg.SvgPathImage).save(buf)
        mimetype = "image/svg+xml"
    else:
        qr.make_image(fill_color="black", back_color="white").save(buf)
        mimetype = "image/png"
    buf.seek(0)
    download = request.args.get("download") == "1"
    return send_file(buf, mimetype=mimetype, as_attachment=download,
                     download_name=f"qr-{slug}.{fmt}")


# ---------- redirect público ----------

@app.route("/r/<slug>")
@app.route("/r/<slug>/")
def go(slug):
    db = get_db()
    row = db.execute("SELECT target FROM codes WHERE slug=?", (slug,)).fetchone()
    if not row:
        abort(404)
    db.execute("UPDATE codes SET scans = scans + 1 WHERE slug=?", (slug,))
    db.commit()
    return redirect(row["target"], code=302)


# ---------- export estático (GitHub Pages) ----------

REDIRECT_HTML = """<!doctype html>
<html><head><meta charset="utf-8">
<meta http-equiv="refresh" content="0; url={target}">
<meta name="robots" content="noindex">
<link rel="canonical" href="{target}">
<title>Redirigiendo…</title>
<script>location.replace({target_js});</script>
</head><body><a href="{target}">Continuar</a></body></html>
"""


def export_static():
    from html import escape
    with app.app_context():
        rows = get_db().execute("SELECT slug, target FROM codes").fetchall()
    rdir = EXPORT_DIR / "r"
    if rdir.exists():
        for old in rdir.iterdir():
            if old.is_dir() and old.name not in {r["slug"] for r in rows}:
                (old / "index.html").unlink(missing_ok=True)
                old.rmdir()
    for r in rows:
        d = rdir / r["slug"]
        d.mkdir(parents=True, exist_ok=True)
        (d / "index.html").write_text(
            REDIRECT_HTML.format(target=escape(r["target"], quote=True),
                                 target_js=json.dumps(r["target"])),
            encoding="utf-8")
    (EXPORT_DIR / ".nojekyll").write_text("", encoding="utf-8")
    (EXPORT_DIR / "index.html").write_text("<!doctype html><title>QR</title>", encoding="utf-8")
    return len(rows)


if __name__ == "__main__":
    import sys
    if "--export" in sys.argv:
        print(f"Exportados {export_static()} redirects en {EXPORT_DIR}")
    else:
        if "--open" in sys.argv:
            import threading
            import webbrowser
            threading.Timer(1.5, webbrowser.open, ["http://127.0.0.1:5000"]).start()
        app.run(host="127.0.0.1", port=5000, debug=False)
