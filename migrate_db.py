
import sqlite3
import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
DATABASE = os.path.join(BASE_DIR, "documents.db")


def migrate_database():
    connection = sqlite3.connect(DATABASE)

    try:
        connection.execute("PRAGMA foreign_keys = ON")

        # Create users table
        connection.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL UNIQUE COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
        """)

        # Check existing document columns
        columns = [
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(documents)"
            ).fetchall()
        ]

        # Add ownership column without deleting existing records
        if "user_id" not in columns:
            connection.execute("""
                ALTER TABLE documents
                ADD COLUMN user_id INTEGER
                REFERENCES users(user_id)
            """)

        connection.execute("""
            CREATE INDEX IF NOT EXISTS
            idx_documents_user_id
            ON documents(user_id)
        """)

        connection.commit()

        print("Database migration completed successfully!")

        print("\nExisting tables:")
        for row in connection.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table'
        """).fetchall():
            print("-", row[0])

        print("\nDocument columns:")
        for row in connection.execute(
            "PRAGMA table_info(documents)"
        ).fetchall():
            print("-", row[1])

    except Exception:
        connection.rollback()
        raise

    finally:
        connection.close()


if __name__ == "__main__":
    migrate_database()
