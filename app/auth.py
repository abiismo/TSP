"""Local account store and server-side sessions shared with the registration module."""

import hashlib
import hmac
import os
import secrets
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path

PASSWORD_ITERATIONS = 600_000
SESSION_SECONDS = 8 * 60 * 60
ATTEMPT_WINDOW = 15 * 60


def normalize_email(value):
    if not isinstance(value, str):
        raise ValueError("Escribe un correo válido.")
    value = value.strip().casefold()
    try:
        value.encode("utf-8")
    except UnicodeError as error:
        raise ValueError("Escribe un correo válido.") from error
    if len(value) > 254 or value.count("@") != 1 or any(c.isspace() for c in value):
        raise ValueError("Escribe un correo válido.")
    local, _, domain = value.partition("@")
    if not local or "." not in domain or domain.startswith(".") or domain.endswith("."):
        raise ValueError("Escribe un correo válido.")
    return value


def password_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PASSWORD_ITERATIONS)


def valid_password_text(value):
    try:
        value.encode("utf-8")
        return True
    except UnicodeError:
        return False


class AuthError(Exception):
    def __init__(self, status, message):
        self.status = status
        super().__init__(message)


class AuthStore:
    def __init__(self, path=None, clock=time.time):
        self.path = Path(path or os.environ.get("TSP_AUTH_DB", "data/auth.sqlite3"))
        self.clock = clock
        # The missing-account path also performs a full password derivation.
        self.dummy_salt = secrets.token_bytes(16)
        self.dummy_hash = secrets.token_bytes(32)

    @contextmanager
    def connection(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        db = sqlite3.connect(self.path, timeout=10)
        try:
            self.path.chmod(0o600)
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA foreign_keys = ON")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY, email TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL, salt BLOB NOT NULL, password_hash BLOB NOT NULL
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    token_hash TEXT PRIMARY KEY, user_id INTEGER NOT NULL REFERENCES users(id),
                    csrf_token TEXT NOT NULL, expires REAL NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    bucket TEXT PRIMARY KEY, failures INTEGER NOT NULL, expires REAL NOT NULL
                );
            """)
            with db:
                db.execute("BEGIN IMMEDIATE")
                yield db
        finally:
            db.close()

    def create_user(self, email, password, name):
        """Registration integration point; never stores or returns the password."""
        email = normalize_email(email)
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 100:
            raise ValueError("El nombre debe tener entre 1 y 100 caracteres.")
        if not isinstance(password, str) or not 15 <= len(password) <= 128 or not valid_password_text(password):
            raise ValueError("La contraseña debe tener entre 15 y 128 caracteres.")
        salt = secrets.token_bytes(16)
        digest = password_hash(password, salt)
        try:
            with self.connection() as db:
                cursor = db.execute(
                    "INSERT INTO users(email,name,salt,password_hash) VALUES(?,?,?,?)",
                    (email, name.strip(), salt, digest),
                )
                return {"id": cursor.lastrowid, "email": email, "name": name.strip()}
        except sqlite3.IntegrityError as error:
            raise ValueError("Ese correo ya está registrado.") from error

    def login(self, email, password, client_ip):
        try:
            email = normalize_email(email)
        except ValueError as error:
            raise AuthError(400, str(error)) from error
        if not isinstance(password, str) or not 1 <= len(password) <= 128 or not valid_password_text(password):
            raise AuthError(400, "Escribe tu contraseña (máximo 128 caracteres).")
        now = self.clock()
        buckets = [("email:" + hashlib.sha256(email.encode()).hexdigest(), 5),
                   ("ip:" + hashlib.sha256(client_ip.encode()).hexdigest(), 20)]
        with self.connection() as db:
            db.execute("DELETE FROM attempts WHERE expires <= ?", (now,))
            db.execute("DELETE FROM sessions WHERE expires <= ?", (now,))
            for bucket, limit in buckets:
                row = db.execute("SELECT failures FROM attempts WHERE bucket=?", (bucket,)).fetchone()
                if row and row["failures"] >= limit:
                    raise AuthError(429, "Demasiados intentos. Espera 15 minutos e inténtalo de nuevo.")
            user = db.execute("SELECT * FROM users WHERE email=?", (email,)).fetchone()
            digest = password_hash(password, user["salt"] if user else self.dummy_salt)
            valid = hmac.compare_digest(digest, user["password_hash"] if user else self.dummy_hash)
            if not user or not valid:
                for bucket, _ in buckets:
                    db.execute("""INSERT INTO attempts VALUES(?,1,?) ON CONFLICT(bucket)
                                  DO UPDATE SET failures=failures+1""", (bucket, now + ATTEMPT_WINDOW))
                # Commit the failed attempt before raising the generic authentication error.
                db.commit()
                raise AuthError(401, "El correo o la contraseña no son correctos.")
            db.execute("DELETE FROM attempts WHERE bucket=?", (buckets[0][0],))
            token = secrets.token_urlsafe(32)
            csrf = secrets.token_urlsafe(32)
            db.execute("INSERT INTO sessions VALUES(?,?,?,?)", (
                hashlib.sha256(token.encode()).hexdigest(), user["id"], csrf, now + SESSION_SECONDS,
            ))
            return token, {"authenticated": True, "user": {
                "id": user["id"], "name": user["name"], "email": user["email"],
            }, "csrf_token": csrf}

    def session(self, token):
        if not token or len(token) > 128:
            return {"authenticated": False}
        with self.connection() as db:
            row = db.execute("""SELECT u.id,u.email,u.name,s.csrf_token FROM sessions s
                JOIN users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires>?""",
                (hashlib.sha256(token.encode()).hexdigest(), self.clock())).fetchone()
            if not row:
                return {"authenticated": False}
            return {"authenticated": True, "user": {
                "id": row["id"], "email": row["email"], "name": row["name"],
            }, "csrf_token": row["csrf_token"]}

    def logout(self, token):
        if token:
            with self.connection() as db:
                db.execute("DELETE FROM sessions WHERE token_hash=?", (hashlib.sha256(token.encode()).hexdigest(),))


if __name__ == "__main__":
    import getpass

    print("Crear una cuenta local para probar el inicio de sesión.")
    try:
        account_email = input("Correo: ")
        account_name = input("Nombre: ")
        account_password = getpass.getpass("Contraseña (15 a 128 caracteres): ")
        if account_password != getpass.getpass("Repite la contraseña: "):
            raise ValueError("Las contraseñas no coinciden.")
        AuthStore().create_user(account_email, account_password, account_name)
        print("Cuenta creada. Ya puedes iniciar sesión en el catálogo.")
    except ValueError as error:
        raise SystemExit(str(error))
