import psycopg2
conn = psycopg2.connect('postgresql://marketlens:S3GUJBRXOCKUjshgxmc6kUC8EMNFUtwY@dpg-da80bou7bikc738pj4g0-a.frankfurt-postgres.render.com/marketlens_rjkx', sslmode='require')
conn.autocommit = True
cur = conn.cursor()
try:
    cur.execute("INSERT INTO products (asin, name, category, amazon_price, rating, review_count, ai_score, estimated_margin_pct, traffic_light) VALUES ('B0TEST001', 'Test Product', 'Kitchen', 29.99, 4.5, 1000, 0.85, 40, 'GREEN') ON CONFLICT (asin) DO NOTHING")
    print('Insert OK')
except Exception as e:
    print('Insert FAILED:', e)
cur.execute('SELECT COUNT(*) FROM products')
print('Total products:', cur.fetchone()[0])
conn.close()
