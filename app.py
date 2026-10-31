
import os
import sqlite3
from datetime import datetime
from uuid import uuid4

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, abort
)
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get(
    "SECRET_KEY", "local-development-key-change-before-deployment"
)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
DATABASE = os.path.join(BASE_DIR, "documents.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "txt", "png", "jpg", "jpeg"
}
CATEGORIES = [
    "Education", "Personal", "Certificates",
    "Finance", "Work", "Other"
]


def connect_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    return db


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                original_name TEXT NOT NULL,
                stored_name TEXT NOT NULL UNIQUE,
                category TEXT NOT NULL,
                file_type TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                upload_date TEXT NOT NULL
            )
        """)


def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS
    )


@app.route("/")
def home():
    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    sql = "SELECT * FROM documents WHERE 1=1"
    params = []

    if query:
        sql += " AND original_name LIKE ?"
        params.append("%" + query + "%")

    if category in CATEGORIES:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY id DESC"

    with connect_db() as db:
        documents = db.execute(sql, params).fetchall()
        total = db.execute(
            "SELECT COUNT(*) FROM documents"
        ).fetchone()[0]
        categories_count = db.execute(
            "SELECT COUNT(DISTINCT category) FROM documents"
        ).fetchone()[0]

    return render_template(
        "index.html",
        documents=documents,
        total=total,
        categories_count=categories_count,
        categories=CATEGORIES,
        selected_category=category,
        query=query
    )


@app.route("/upload", methods=["POST"])
def upload():
    file = request.files.get("document")
    category = request.form.get("category", "")

    if not file or not file.filename:
        flash("Please choose a file.", "error")
        return redirect(url_for("home"))

    if category not in CATEGORIES:
        flash("Choose a valid category.", "error")
        return redirect(url_for("home"))

    if not allowed_file(file.filename):
        flash("Unsupported file type.", "error")
        return redirect(url_for("home"))

    original_name = secure_filename(file.filename)
    if not original_name:
        flash("Invalid filename.", "error")
        return redirect(url_for("home"))

    stored_name = uuid4().hex + "_" + original_name
    path = os.path.join(UPLOAD_FOLDER, stored_name)

    try:
        file.save(path)
        size = os.path.getsize(path)

        with connect_db() as db:
            db.execute("""
                INSERT INTO documents
                (original_name, stored_name, category, file_type,
                 file_size, upload_date)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (
                original_name, stored_name, category,
                original_name.rsplit(".", 1)[1].lower(),
                size, datetime.now().strftime("%d %b %Y, %I:%M %p")
            ))

        flash("Document uploaded successfully!", "success")

    except Exception:
        if os.path.exists(path):
            os.remove(path)
        app.logger.exception("Upload failed")
        flash("Upload failed. Check the terminal for details.", "error")

    return redirect(url_for("home"))


@app.route("/download/<int:doc_id>")
def download(doc_id):
    with connect_db() as db:
        doc = db.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()

    if not doc:
        abort(404)

    return send_from_directory(
        UPLOAD_FOLDER,
        doc["stored_name"],
        as_attachment=True,
        download_name=doc["original_name"]
    )


@app.route("/rename/<int:doc_id>", methods=["POST"])
def rename(doc_id):
    new_name = secure_filename(
        request.form.get("new_name", "").strip()
    )

    if not new_name or "." not in new_name:
        flash("Enter a valid filename with its extension.", "error")
        return redirect(url_for("home"))

    with connect_db() as db:
        doc = db.execute(
            "SELECT id, file_type FROM documents WHERE id = ?",
            (doc_id,)
        ).fetchone()

        if not doc:
            abort(404)

        if new_name.rsplit(".", 1)[1].lower() != doc["file_type"]:
            flash("Keep the original file extension.", "error")
            return redirect(url_for("home"))

        db.execute(
            "UPDATE documents SET original_name = ? WHERE id = ?",
            (new_name, doc_id)
        )

    flash("Document name updated.", "success")
    return redirect(url_for("home"))


@app.route("/delete/<int:doc_id>", methods=["POST"])
def delete(doc_id):
    with connect_db() as db:
        doc = db.execute(
            "SELECT * FROM documents WHERE id = ?", (doc_id,)
        ).fetchone()

        if not doc:
            abort(404)

        db.execute("DELETE FROM documents WHERE id = ?", (doc_id,))

    path = os.path.join(UPLOAD_FOLDER, doc["stored_name"])
    if os.path.isfile(path):
        os.remove(path)

    flash("Document deleted.", "success")
    return redirect(url_for("home"))


@app.template_filter("filesize")
def filesize(size):
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    return f"{size / (1024 * 1024):.2f} MB"


@app.errorhandler(413)
def too_large(error):
    flash("File exceeds the 10 MB upload limit.", "error")
    return redirect(url_for("home"))


init_db()

if __name__ == "__main__":
    app.run(debug=True)
