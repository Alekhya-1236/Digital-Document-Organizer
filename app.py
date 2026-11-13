
import os
import sqlite3
from datetime import datetime
from uuid import uuid4
from contextlib import closing

from flask import (
    Flask, render_template, request, redirect,
    url_for, flash, send_from_directory, abort
)
from flask_login import (
    LoginManager, UserMixin, login_user,
    login_required, logout_user, current_user
)
from flask_wtf.csrf import CSRFProtect
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename


# --------------------------------------------------
# 1. FLASK CONFIGURATION
# --------------------------------------------------


app = Flask(__name__)

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# Railway persistent volume directory.
# Locally, use the project folder.
DATA_DIR = os.environ.get("DATA_DIR", BASE_DIR)

os.makedirs(DATA_DIR, exist_ok=True)

UPLOAD_FOLDER = os.path.join(DATA_DIR, "uploads")
DATABASE = os.path.join(DATA_DIR, "documents.db")

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# Secret key configuration
SECRET_KEY = os.environ.get("SECRET_KEY")

if not SECRET_KEY and os.environ.get("APP_ENV") == "production":
    raise RuntimeError("SECRET_KEY must be configured in production.")

app.secret_key = SECRET_KEY or "local-development-key-change-before-deployment"

app.config.update(
    UPLOAD_FOLDER=UPLOAD_FOLDER,
    MAX_CONTENT_LENGTH=10 * 1024 * 1024,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=os.environ.get("APP_ENV") == "production"
)
# Flask-Login configuration
login_manager = LoginManager()
login_manager.init_app(app)

login_manager.login_view = "login"
login_manager.login_message = "Please log in to access your dashboard."
login_manager.login_message_category = "error"

# CSRF protection
csrf = CSRFProtect(app)



# --------------------------------------------------
# 2. APPLICATION CONSTANTS
# --------------------------------------------------

ALLOWED_EXTENSIONS = {
    "pdf", "doc", "docx", "txt", "png", "jpg", "jpeg"
}

CATEGORIES = [
    "Education", "Personal", "Certificates",
    "Finance", "Work", "Other"
]


# --------------------------------------------------
# 3. DATABASE CONNECTION
# --------------------------------------------------

def connect_db():
    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    return db


# --------------------------------------------------
# 4. DATABASE INITIALIZATION AND MIGRATION
# --------------------------------------------------

def init_db():
    with closing(connect_db()) as db:

        db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

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

        columns = [
            row["name"]
            for row in db.execute(
                "PRAGMA table_info(documents)"
            ).fetchall()
        ]

        if "user_id" not in columns:
            db.execute("""
                ALTER TABLE documents
                ADD COLUMN user_id INTEGER
                REFERENCES users(user_id)
            """)

        db.execute("""
            CREATE INDEX IF NOT EXISTS idx_documents_user_id
            ON documents(user_id)
        """)

        db.commit()

    print("Database initialized successfully!")


# --------------------------------------------------
# 5. USER MODEL
# --------------------------------------------------

class User(UserMixin):

    def __init__(self, user_id, name, email):
        self.id = str(user_id)
        self.name = name
        self.email = email


@login_manager.user_loader
def load_user(user_id):

    with closing(connect_db()) as db:
        user = db.execute("""
            SELECT user_id, name, email
            FROM users
            WHERE user_id = ?
        """, (user_id,)).fetchone()

    if user:
        return User(
            user["user_id"],
            user["name"],
            user["email"]
        )

    return None


# --------------------------------------------------
# 6. HELPER FUNCTIONS
# --------------------------------------------------

def allowed_file(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_EXTENSIONS
    )


def get_owned_document(doc_id):

    with closing(connect_db()) as db:
        doc = db.execute("""
            SELECT * FROM documents
            WHERE id = ? AND user_id = ?
        """, (doc_id, current_user.id)).fetchone()

    if not doc:
        abort(404)

    return doc


# --------------------------------------------------
# 7. REGISTRATION
# --------------------------------------------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        confirm_password = request.form.get(
            "confirm_password", ""
        )

        if not name or not email or not password:
            flash("All fields are required.", "error")
            return redirect(url_for("register"))

        if len(name) > 100 or len(email) > 254:
            flash("Name or email is too long.", "error")
            return redirect(url_for("register"))

        if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
            flash("Enter a valid email address.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("register"))

        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        try:
            with closing(connect_db()) as db:

                user_count = db.execute(
                    "SELECT COUNT(*) FROM users"
                ).fetchone()[0]

                cursor = db.execute("""
                    INSERT INTO users
                    (name, email, password_hash, created_at)
                    VALUES (?, ?, ?, ?)
                """, (
                    name,
                    email,
                    password_hash,
                    datetime.now().strftime(
                        "%d %b %Y, %I:%M %p"
                    )
                ))

                new_user_id = cursor.lastrowid

                # Give the first registered account ownership
                # of documents created before authentication.
                if user_count == 0:
                    db.execute("""
                        UPDATE documents
                        SET user_id = ?
                        WHERE user_id IS NULL
                    """, (new_user_id,))

                db.commit()

            flash("Account created successfully! Please log in.", "success")
            return redirect(url_for("login"))

        except sqlite3.IntegrityError:
            flash("An account with this email already exists.", "error")

        except Exception:
            app.logger.exception("Registration failed")
            flash("Registration failed. Please try again.", "error")

    return render_template("register.html")


# --------------------------------------------------
# 8. LOGIN
# --------------------------------------------------

@app.route("/login", methods=["GET", "POST"])
def login():

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    if request.method == "POST":

        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        with closing(connect_db()) as db:
            user = db.execute("""
                SELECT * FROM users
                WHERE email = ?
            """, (email,)).fetchone()

        if user and check_password_hash(
            user["password_hash"], password
        ):

            account = User(
                user["user_id"],
                user["name"],
                user["email"]
            )

            login_user(account, fresh=True)

            flash("Welcome back!", "success")

            next_page = request.args.get("next")

            # Only allow local application paths.
            if next_page and next_page.startswith("/") and not next_page.startswith("//"):
                return redirect(next_page)

            return redirect(url_for("home"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


# --------------------------------------------------
# 9. LOGOUT
# --------------------------------------------------

@app.route("/logout", methods=["POST"])
@login_required
def logout():

    logout_user()
    flash("You have been logged out.", "success")

    return redirect(url_for("login"))


# --------------------------------------------------
# 10. DASHBOARD
# --------------------------------------------------

@app.route("/")
@login_required
def home():

    query = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    sql = """
        SELECT * FROM documents
        WHERE user_id = ?
    """

    params = [current_user.id]

    if query:
        sql += " AND original_name LIKE ?"
        params.append("%" + query + "%")

    if category in CATEGORIES:
        sql += " AND category = ?"
        params.append(category)

    sql += " ORDER BY id DESC"

    with closing(connect_db()) as db:

        documents = db.execute(sql, params).fetchall()

        total = db.execute("""
            SELECT COUNT(*) FROM documents
            WHERE user_id = ?
        """, (current_user.id,)).fetchone()[0]

        categories_count = db.execute("""
            SELECT COUNT(DISTINCT category)
            FROM documents
            WHERE user_id = ?
        """, (current_user.id,)).fetchone()[0]

    return render_template(
        "index.html",
        documents=documents,
        total=total,
        categories_count=categories_count,
        categories=CATEGORIES,
        selected_category=category,
        query=query
    )


# --------------------------------------------------
# 11. UPLOAD DOCUMENT
# --------------------------------------------------

@app.route("/upload", methods=["POST"])
@login_required
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

        with closing(connect_db()) as db:
            db.execute("""
                INSERT INTO documents
                (original_name, stored_name, category,
                 file_type, file_size, upload_date, user_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                original_name,
                stored_name,
                category,
                original_name.rsplit(".", 1)[1].lower(),
                size,
                datetime.now().strftime("%d %b %Y, %I:%M %p"),
                current_user.id
            ))

            db.commit()

        flash("Document uploaded successfully!", "success")

    except Exception:
        if os.path.exists(path):
            os.remove(path)

        app.logger.exception("Upload failed")
        flash("Upload failed. Please try again.", "error")

    return redirect(url_for("home"))


# --------------------------------------------------
# 12. DOWNLOAD DOCUMENT
# --------------------------------------------------

@app.route("/download/<int:doc_id>")
@login_required
def download(doc_id):

    doc = get_owned_document(doc_id)

    path = os.path.join(UPLOAD_FOLDER, doc["stored_name"])

    if not os.path.isfile(path):
        abort(404)

    return send_from_directory(
        UPLOAD_FOLDER,
        doc["stored_name"],
        as_attachment=True,
        download_name=doc["original_name"]
    )


# --------------------------------------------------
# 13. RENAME DOCUMENT
# --------------------------------------------------

@app.route("/rename/<int:doc_id>", methods=["POST"])
@login_required
def rename(doc_id):

    doc = get_owned_document(doc_id)

    new_name = secure_filename(
        request.form.get("new_name", "").strip()
    )

    if not new_name or "." not in new_name:
        flash("Enter a valid filename with its extension.", "error")
        return redirect(url_for("home"))

    if new_name.rsplit(".", 1)[1].lower() != doc["file_type"]:
        flash("Keep the original file extension.", "error")
        return redirect(url_for("home"))

    with closing(connect_db()) as db:
        db.execute("""
            UPDATE documents
            SET original_name = ?
            WHERE id = ? AND user_id = ?
        """, (new_name, doc_id, current_user.id))

        db.commit()

    flash("Document name updated.", "success")
    return redirect(url_for("home"))


# --------------------------------------------------
# 14. DELETE DOCUMENT
# --------------------------------------------------

@app.route("/delete/<int:doc_id>", methods=["POST"])
@login_required
def delete(doc_id):

    doc = get_owned_document(doc_id)

    with closing(connect_db()) as db:
        db.execute("""
            DELETE FROM documents
            WHERE id = ? AND user_id = ?
        """, (doc_id, current_user.id))

        db.commit()

    path = os.path.join(UPLOAD_FOLDER, doc["stored_name"])

    if os.path.isfile(path):
        os.remove(path)

    flash("Document deleted.", "success")
    return redirect(url_for("home"))


# --------------------------------------------------
# 15. FILE SIZE FILTER
# --------------------------------------------------

@app.template_filter("filesize")
def filesize(size):

    if size < 1024:
        return f"{size} B"

    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"

    return f"{size / (1024 * 1024):.2f} MB"


# --------------------------------------------------
# 16. ERROR HANDLING
# --------------------------------------------------

@app.errorhandler(413)
def too_large(error):

    flash("File exceeds the 10 MB upload limit.", "error")

    if current_user.is_authenticated:
        return redirect(url_for("home"))

    return redirect(url_for("login"))


# --------------------------------------------------
# 17. START APPLICATION
# --------------------------------------------------

# --------------------------------------------------
# 17. HEALTH CHECK AND START APPLICATION
# --------------------------------------------------

@app.route("/health")
def health():
    return {"status": "healthy"}, 200


init_db()

if __name__ == "__main__":
    app.run(
        debug=os.environ.get("FLASK_DEBUG") == "1"
    )
