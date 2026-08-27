"""Run database migration against Render PostgreSQL."""
import psycopg2
import os

DATABASE_URL = "postgresql://marketlens:S3GUJBRXOCKUjshgxmc6kUC8EMNFUtwY@dpg-da80bou7bikc738pj4g0-a.frankfurt-postgres.render.com/marketlens_rjkx"

MIGRATION_FILE = os.path.join(os.path.dirname(__file__), "online_db", "migrations", "001_init.sql")

print(f"Connecting to database...")
conn = psycopg2.connect(DATABASE_URL, sslmode="require")
conn.autocommit = True
cur = conn.cursor()

print(f"Running migration: {MIGRATION_FILE}")
with open(MIGRATION_FILE, "r", encoding="utf-8") as f:
    sql = f.read()
cur.execute(sql)

print("Verifying tables...")
cur.execute("""
    SELECT table_name FROM information_schema.tables 
    WHERE table_schema = 'public' ORDER BY table_name;
""")
tables = [row[0] for row in cur.fetchall()]
print(f"Tables created ({len(tables)}): {', '.join(tables)}")

cur.close()
conn.close()
print("Migration complete!")
