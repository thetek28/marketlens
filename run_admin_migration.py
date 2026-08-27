"""Run admin migration against Render PostgreSQL."""
import psycopg2
import os

DATABASE_URL = "postgresql://marketlens:S3GUJBRXOCKUjshgxmc6kUC8EMNFUtwY@dpg-da80bou7bikc738pj4g0-a.frankfurt-postgres.render.com/marketlens_rjkx"

MIGRATION_FILE = os.path.join(os.path.dirname(__file__), "online_db", "migrations", "002_admin.sql")

print("Connecting to database...")
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
conn.autocommit = True
cur = conn.cursor()

print(f"Running migration: {MIGRATION_FILE}")
with open(MIGRATION_FILE, "r", encoding="utf-8") as f:
    sql = f.read()
cur.execute(sql)

print("Verifying admin tables...")
cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema = 'public' AND table_name LIKE 'admin_%' ORDER BY table_name;
""")
tables = [row[0] for row in cur.fetchall()]
print(f"Admin tables ({len(tables)}): {', '.join(tables)}")

cur.execute("SELECT COUNT(*) FROM admin_plans")
plans = cur.fetchone()[0]
print(f"Plans: {plans}")

cur.execute("SELECT COUNT(*) FROM admin_roles")
roles = cur.fetchone()[0]
print(f"Roles: {roles}")

cur.close()
conn.close()
print("Admin migration complete!")
