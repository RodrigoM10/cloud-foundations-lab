import csv
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import execute_values

ROOT    = Path(__file__).resolve().parents[1]
SQL_DIR = ROOT / "sql"
DATA    = ROOT / "data" / "raw" / "olist"


def run_sql(cur, path):
    cur.execute(path.read_text())


def load_csv(cur, table, path, transform=None):
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    if transform:
        rows = [transform(r) for r in rows]

    if not rows:
        return 0

    cols = list(rows[0].keys())
    values = [[r[c] or None for c in cols] for r in rows]

    execute_values(
        cur,
        f"INSERT INTO {table} ({','.join(cols)}) VALUES %s ON CONFLICT DO NOTHING",
        values,
    )

    return len(rows)


def ts(val):
    return val if val else None


def main():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "localhost"),
        port=int(os.getenv("POSTGRES_PORT", "5432")),
        user=os.getenv("POSTGRES_USER", "postgres"),
        password=os.getenv("POSTGRES_PASSWORD", "postgres"),
        dbname=os.getenv("POSTGRES_DB", "course"),
    )
    conn.autocommit = True
    cur = conn.cursor()

    print("Creando schema...")
    run_sql(cur, SQL_DIR / "001_schema.sql")

    print("Cargando datos...")

    n = load_csv(cur, "category_translations", DATA / "category_translations.csv",
                 lambda r: {"category_name_pt": r["product_category_name"],
                            "category_name_en":  r["product_category_name_english"]})
    print(f"  category_translations: {n}")

    n = load_csv(cur, "customers", DATA / "customers.csv",
                 lambda r: {"customer_id":        r["customer_id"],
                            "customer_unique_id":  r["customer_unique_id"],
                            "customer_zip_code":   r["customer_zip_code_prefix"],
                            "customer_city":       r["customer_city"],
                            "customer_state":      r["customer_state"]})
    print(f"  customers:             {n}")

    n = load_csv(cur, "sellers", DATA / "sellers.csv",
                 lambda r: {"seller_id":       r["seller_id"],
                            "seller_zip_code": r["seller_zip_code_prefix"],
                            "seller_city":     r["seller_city"],
                            "seller_state":    r["seller_state"]})
    print(f"  sellers:               {n}")

    n = load_csv(cur, "products", DATA / "products.csv",
                 lambda r: {"product_id":           r["product_id"],
                            "category_name":         r["product_category_name"] or None,
                            "name_length":           r["product_name_lenght"] or None,
                            "description_length":    r["product_description_lenght"] or None,
                            "photos_qty":            r["product_photos_qty"] or None,
                            "weight_g":              r["product_weight_g"] or None,
                            "length_cm":             r["product_length_cm"] or None,
                            "height_cm":             r["product_height_cm"] or None,
                            "width_cm":              r["product_width_cm"] or None})
    print(f"  products:              {n}")

    n = load_csv(cur, "orders", DATA / "orders.csv",
                 lambda r: {"order_id":                r["order_id"],
                            "customer_id":             r["customer_id"],
                            "order_status":            r["order_status"],
                            "purchase_timestamp":      ts(r["order_purchase_timestamp"]),
                            "approved_at":             ts(r["order_approved_at"]),
                            "delivered_carrier_date":  ts(r["order_delivered_carrier_date"]),
                            "delivered_customer_date": ts(r["order_delivered_customer_date"]),
                            "estimated_delivery_date": ts(r["order_estimated_delivery_date"])})
    print(f"  orders:                {n}")

    n = load_csv(cur, "order_items", DATA / "order_items.csv",
                 lambda r: {"order_id":           r["order_id"],
                            "order_item_id":      r["order_item_id"],
                            "product_id":         r["product_id"],
                            "seller_id":          r["seller_id"],
                            "shipping_limit_date":ts(r["shipping_limit_date"]),
                            "price":              r["price"],
                            "freight_value":      r["freight_value"]})
    print(f"  order_items:           {n}")

    n = load_csv(cur, "order_payments", DATA / "order_payments.csv",
                 lambda r: {"order_id":             r["order_id"],
                            "payment_sequential":   r["payment_sequential"],
                            "payment_type":         r["payment_type"],
                            "payment_installments": r["payment_installments"],
                            "payment_value":        r["payment_value"]})
    print(f"  order_payments:        {n}")

    n = load_csv(cur, "order_reviews", DATA / "order_reviews.csv",
                 lambda r: {"review_id":               r["review_id"],
                            "order_id":                r["order_id"],
                            "review_score":            r["review_score"],
                            "review_comment_title":    r["review_comment_title"] or None,
                            "review_comment_message":  r["review_comment_message"] or None,
                            "review_creation_date":    ts(r["review_creation_date"]),
                            "review_answer_timestamp": ts(r["review_answer_timestamp"])})
    print(f"  order_reviews:         {n}")

    cur.close()
    conn.close()
    print("\nBase de datos cargada.")


if __name__ == "__main__":
    main()
