"""Seed the super_admin account in PostgreSQL."""
import os
import sys
import psycopg2
import psycopg2.extras
import bcrypt

DATABASE_URL = os.environ.get("DATABASE_URL", "")
if not DATABASE_URL:
    print("ERROR: DATABASE_URL not set")
    sys.exit(1)

ADMIN_USER = os.environ.get("ADMIN_USER", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASS", "admin123")
ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@marketlens.com")

pw_hash = bcrypt.hashpw(ADMIN_PASS.encode(), bcrypt.gensalt()).decode()

conn = psycopg2.connect(DATABASE_URL, sslmode="require")
try:
    with conn.cursor() as cur:
        cur.execute(
            """INSERT INTO admin_users (username, email, password_hash, role, display_name)
               VALUES (%s, %s, %s, %s, %s)
               ON CONFLICT (username) DO UPDATE SET
                 email = EXCLUDED.email,
                 password_hash = EXCLUDED.password_hash,
                 role = EXCLUDED.role,
                 updated_at = CURRENT_TIMESTAMP
               RETURNING id, username, role""",
            (ADMIN_USER, ADMIN_EMAIL, pw_hash, "super_admin", "Super Admin")
        )
        row = cur.fetchone()
        conn.commit()
        if row:
            print(f"Admin seeded: id={row[0]}, username={row[1]}, role={row[2]}")
        else:
            print("Admin already exists (no changes)")
except Exception as e:
    conn.rollback()
    print(f"Error: {e}")
    sys.exit(1)
finally:
    conn.close()
