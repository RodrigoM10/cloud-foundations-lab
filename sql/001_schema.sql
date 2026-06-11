-- Schema: Olist Brazilian E-Commerce (sample)
-- Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
-- License: CC BY-NC-SA 4.0 — https://creativecommons.org/licenses/by-nc-sa/4.0/
-- Attribution: Olist (https://olist.com)

CREATE TABLE IF NOT EXISTS customers (
    customer_id             TEXT PRIMARY KEY,
    customer_unique_id      TEXT NOT NULL,
    customer_zip_code       TEXT,
    customer_city           TEXT,
    customer_state          TEXT
);

CREATE TABLE IF NOT EXISTS sellers (
    seller_id               TEXT PRIMARY KEY,
    seller_zip_code         TEXT,
    seller_city             TEXT,
    seller_state            TEXT
);

CREATE TABLE IF NOT EXISTS category_translations (
    category_name_pt        TEXT PRIMARY KEY,
    category_name_en        TEXT
);

CREATE TABLE IF NOT EXISTS products (
    product_id              TEXT PRIMARY KEY,
    category_name           TEXT REFERENCES category_translations(category_name_pt),
    name_length             INTEGER,
    description_length      INTEGER,
    photos_qty              INTEGER,
    weight_g                NUMERIC,
    length_cm               NUMERIC,
    height_cm               NUMERIC,
    width_cm                NUMERIC
);

CREATE TABLE IF NOT EXISTS orders (
    order_id                TEXT PRIMARY KEY,
    customer_id             TEXT REFERENCES customers(customer_id),
    order_status            TEXT NOT NULL,
    purchase_timestamp      TIMESTAMP,
    approved_at             TIMESTAMP,
    delivered_carrier_date  TIMESTAMP,
    delivered_customer_date TIMESTAMP,
    estimated_delivery_date TIMESTAMP
);

CREATE TABLE IF NOT EXISTS order_items (
    order_id                TEXT REFERENCES orders(order_id),
    order_item_id           INTEGER,
    product_id              TEXT REFERENCES products(product_id),
    seller_id               TEXT REFERENCES sellers(seller_id),
    shipping_limit_date     TIMESTAMP,
    price                   NUMERIC NOT NULL,
    freight_value           NUMERIC NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS order_payments (
    order_id                TEXT REFERENCES orders(order_id),
    payment_sequential      INTEGER,
    payment_type            TEXT NOT NULL,
    payment_installments    INTEGER,
    payment_value           NUMERIC NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS order_reviews (
    review_id               TEXT PRIMARY KEY,
    order_id                TEXT REFERENCES orders(order_id),
    review_score            INTEGER CHECK (review_score BETWEEN 1 AND 5),
    review_comment_title    TEXT,
    review_comment_message  TEXT,
    review_creation_date    TIMESTAMP,
    review_answer_timestamp TIMESTAMP
);
