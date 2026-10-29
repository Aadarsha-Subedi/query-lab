-- The Olist demo dataset (Brazilian e-commerce, about 100k orders).
-- Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce
-- Licence: CC BY-NC-SA 4.0 (non-commercial).
-- Tables are filled by `manage.py load_demo`. Every date is shifted forward
-- by DEMO_DATE_SHIFT_DAYS so the newest order lands in a recent month.
-- Idempotent. The schema name is the placeholder in braces.

CREATE TABLE IF NOT EXISTS {schema}.customers (
    customer_id              text PRIMARY KEY,
    customer_unique_id       text NOT NULL,
    customer_zip_code_prefix text NOT NULL,
    customer_city            text NOT NULL,
    customer_state           text NOT NULL
);

CREATE TABLE IF NOT EXISTS {schema}.sellers (
    seller_id              text PRIMARY KEY,
    seller_zip_code_prefix text NOT NULL,
    seller_city            text NOT NULL,
    seller_state           text NOT NULL
);

CREATE TABLE IF NOT EXISTS {schema}.product_category_translation (
    product_category_name         text PRIMARY KEY,
    product_category_name_english text NOT NULL
);

CREATE TABLE IF NOT EXISTS {schema}.products (
    product_id                 text PRIMARY KEY,
    product_category_name      text,
    product_name_length        integer,
    product_description_length integer,
    product_photos_qty         integer,
    product_weight_g           integer,
    product_length_cm          integer,
    product_height_cm          integer,
    product_width_cm           integer
);

CREATE TABLE IF NOT EXISTS {schema}.orders (
    order_id                      text PRIMARY KEY,
    customer_id                   text NOT NULL REFERENCES {schema}.customers (customer_id),
    order_status                  text NOT NULL,
    order_purchase_timestamp      timestamp NOT NULL,
    order_approved_at             timestamp,
    order_delivered_carrier_date  timestamp,
    order_delivered_customer_date timestamp,
    order_estimated_delivery_date timestamp NOT NULL
);

CREATE TABLE IF NOT EXISTS {schema}.order_items (
    order_id            text NOT NULL REFERENCES {schema}.orders (order_id),
    order_item_id       integer NOT NULL,
    product_id          text NOT NULL REFERENCES {schema}.products (product_id),
    seller_id           text NOT NULL REFERENCES {schema}.sellers (seller_id),
    shipping_limit_date timestamp NOT NULL,
    price               numeric(10, 2) NOT NULL,
    freight_value       numeric(10, 2) NOT NULL,
    PRIMARY KEY (order_id, order_item_id)
);

CREATE TABLE IF NOT EXISTS {schema}.order_payments (
    order_id             text NOT NULL REFERENCES {schema}.orders (order_id),
    payment_sequential   integer NOT NULL,
    payment_type         text NOT NULL,
    payment_installments integer NOT NULL,
    payment_value        numeric(10, 2) NOT NULL,
    PRIMARY KEY (order_id, payment_sequential)
);

CREATE TABLE IF NOT EXISTS {schema}.order_reviews (
    review_id               text NOT NULL,
    order_id                text NOT NULL REFERENCES {schema}.orders (order_id),
    review_score            integer NOT NULL,
    review_comment_title    text,
    review_comment_message  text,
    review_creation_date    timestamp NOT NULL,
    review_answer_timestamp timestamp NOT NULL,
    PRIMARY KEY (review_id, order_id)
);

CREATE TABLE IF NOT EXISTS {schema}.geolocation (
    geolocation_id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    geolocation_zip_code_prefix text NOT NULL,
    geolocation_lat             double precision NOT NULL,
    geolocation_lng             double precision NOT NULL,
    geolocation_city            text NOT NULL,
    geolocation_state           text NOT NULL
);

-- Indexes on foreign keys (and the zip prefix used to join geolocation).
-- Composite primary keys already cover order_items.order_id and
-- order_payments.order_id.
CREATE INDEX IF NOT EXISTS orders_customer_id_idx ON {schema}.orders (customer_id);
CREATE INDEX IF NOT EXISTS order_items_product_id_idx ON {schema}.order_items (product_id);
CREATE INDEX IF NOT EXISTS order_items_seller_id_idx ON {schema}.order_items (seller_id);
CREATE INDEX IF NOT EXISTS order_reviews_order_id_idx ON {schema}.order_reviews (order_id);
CREATE INDEX IF NOT EXISTS geolocation_zip_code_prefix_idx
    ON {schema}.geolocation (geolocation_zip_code_prefix);

-- Plain-English descriptions. Step 1 puts these into the agent's prompt.

COMMENT ON TABLE {schema}.customers IS
    'One row per customer per order. The same person can have several customer_id values; customer_unique_id identifies the person.';
COMMENT ON COLUMN {schema}.customers.customer_id IS 'Key for this customer record; each order has its own customer_id.';
COMMENT ON COLUMN {schema}.customers.customer_unique_id IS 'Identifies the person across orders. Use it to count unique or repeat customers.';
COMMENT ON COLUMN {schema}.customers.customer_zip_code_prefix IS 'First five digits of the customer''s Brazilian postal code (CEP).';
COMMENT ON COLUMN {schema}.customers.customer_city IS 'Customer city, lower case, without accents.';
COMMENT ON COLUMN {schema}.customers.customer_state IS 'Two-letter Brazilian state code, for example SP or RJ.';

COMMENT ON TABLE {schema}.sellers IS 'Marketplace sellers who fulfil order items.';
COMMENT ON COLUMN {schema}.sellers.seller_id IS 'Key for the seller.';
COMMENT ON COLUMN {schema}.sellers.seller_zip_code_prefix IS 'First five digits of the seller''s postal code (CEP).';
COMMENT ON COLUMN {schema}.sellers.seller_city IS 'Seller city, lower case, without accents.';
COMMENT ON COLUMN {schema}.sellers.seller_state IS 'Two-letter Brazilian state code.';

COMMENT ON TABLE {schema}.product_category_translation IS
    'Portuguese product category names and their English translations. products already stores the English name.';
COMMENT ON COLUMN {schema}.product_category_translation.product_category_name IS 'Category name in Portuguese, as in the original data.';
COMMENT ON COLUMN {schema}.product_category_translation.product_category_name_english IS 'Category name in English.';

COMMENT ON TABLE {schema}.products IS 'Products sold on the marketplace.';
COMMENT ON COLUMN {schema}.products.product_id IS 'Key for the product.';
COMMENT ON COLUMN {schema}.products.product_category_name IS
    'Product category in English, for example health_beauty. NULL when unknown; two categories without a translation keep their Portuguese name.';
COMMENT ON COLUMN {schema}.products.product_name_length IS 'Number of characters in the product name.';
COMMENT ON COLUMN {schema}.products.product_description_length IS 'Number of characters in the product description.';
COMMENT ON COLUMN {schema}.products.product_photos_qty IS 'Number of published product photos.';
COMMENT ON COLUMN {schema}.products.product_weight_g IS 'Product weight in grams.';
COMMENT ON COLUMN {schema}.products.product_length_cm IS 'Product length in centimetres.';
COMMENT ON COLUMN {schema}.products.product_height_cm IS 'Product height in centimetres.';
COMMENT ON COLUMN {schema}.products.product_width_cm IS 'Product width in centimetres.';

COMMENT ON TABLE {schema}.orders IS 'One row per order, with its status and the timestamps of each step.';
COMMENT ON COLUMN {schema}.orders.order_id IS 'Key for the order.';
COMMENT ON COLUMN {schema}.orders.customer_id IS 'The customer record that placed the order (customers.customer_id).';
COMMENT ON COLUMN {schema}.orders.order_status IS
    'Order status: delivered, shipped, canceled, unavailable, invoiced, processing, created or approved.';
COMMENT ON COLUMN {schema}.orders.order_purchase_timestamp IS 'When the customer placed the order. Use this as the order date.';
COMMENT ON COLUMN {schema}.orders.order_approved_at IS 'When the payment was approved. NULL if never approved.';
COMMENT ON COLUMN {schema}.orders.order_delivered_carrier_date IS 'When the order was handed to the carrier. NULL if not yet shipped.';
COMMENT ON COLUMN {schema}.orders.order_delivered_customer_date IS 'When the customer received the order. NULL if not delivered.';
COMMENT ON COLUMN {schema}.orders.order_estimated_delivery_date IS 'Delivery date promised to the customer at purchase.';

COMMENT ON TABLE {schema}.order_items IS 'Items in each order. An order with three items has three rows.';
COMMENT ON COLUMN {schema}.order_items.order_id IS 'The order (orders.order_id).';
COMMENT ON COLUMN {schema}.order_items.order_item_id IS 'Position of the item within the order, starting at 1.';
COMMENT ON COLUMN {schema}.order_items.product_id IS 'The product sold (products.product_id).';
COMMENT ON COLUMN {schema}.order_items.seller_id IS 'The seller who fulfilled the item (sellers.seller_id).';
COMMENT ON COLUMN {schema}.order_items.shipping_limit_date IS 'Deadline for the seller to hand the item to the carrier.';
COMMENT ON COLUMN {schema}.order_items.price IS 'Item price in Brazilian reais (BRL).';
COMMENT ON COLUMN {schema}.order_items.freight_value IS 'Shipping cost for the item in BRL. Order revenue is price plus freight.';

COMMENT ON TABLE {schema}.order_payments IS 'Payments for each order. An order paid with two methods has two rows.';
COMMENT ON COLUMN {schema}.order_payments.order_id IS 'The order (orders.order_id).';
COMMENT ON COLUMN {schema}.order_payments.payment_sequential IS 'Sequence number of the payment within the order, starting at 1.';
COMMENT ON COLUMN {schema}.order_payments.payment_type IS 'Payment method: credit_card, boleto, voucher, debit_card or not_defined.';
COMMENT ON COLUMN {schema}.order_payments.payment_installments IS 'Number of instalments the customer chose.';
COMMENT ON COLUMN {schema}.order_payments.payment_value IS 'Amount paid in BRL.';

COMMENT ON TABLE {schema}.order_reviews IS 'Customer reviews of orders, from 1 (worst) to 5 (best).';
COMMENT ON COLUMN {schema}.order_reviews.review_id IS 'Review identifier. A few reviews cover more than one order.';
COMMENT ON COLUMN {schema}.order_reviews.order_id IS 'The reviewed order (orders.order_id).';
COMMENT ON COLUMN {schema}.order_reviews.review_score IS 'Score from 1 to 5.';
COMMENT ON COLUMN {schema}.order_reviews.review_comment_title IS 'Review title in Portuguese. Often NULL.';
COMMENT ON COLUMN {schema}.order_reviews.review_comment_message IS 'Review text in Portuguese. Often NULL.';
COMMENT ON COLUMN {schema}.order_reviews.review_creation_date IS 'When the satisfaction survey was sent to the customer.';
COMMENT ON COLUMN {schema}.order_reviews.review_answer_timestamp IS 'When the customer answered the survey.';

COMMENT ON TABLE {schema}.geolocation IS
    'Coordinates for Brazilian postal code prefixes. Several rows per prefix; join on the prefix and aggregate.';
COMMENT ON COLUMN {schema}.geolocation.geolocation_id IS 'Surrogate key (the source data has none).';
COMMENT ON COLUMN {schema}.geolocation.geolocation_zip_code_prefix IS 'First five digits of the postal code (CEP).';
COMMENT ON COLUMN {schema}.geolocation.geolocation_lat IS 'Latitude.';
COMMENT ON COLUMN {schema}.geolocation.geolocation_lng IS 'Longitude.';
COMMENT ON COLUMN {schema}.geolocation.geolocation_city IS 'City name.';
COMMENT ON COLUMN {schema}.geolocation.geolocation_state IS 'Two-letter Brazilian state code.';
