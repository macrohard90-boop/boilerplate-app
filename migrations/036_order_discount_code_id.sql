-- 036: Add discount_code_id to orders for coupon usage tracking
-- Currently the link between order and coupon is lost after checkout
-- (cart has discount_code_id but order does not). This enables coupon
-- usage history queries.

-- UP

ALTER TABLE ecommerce.orders
    ADD COLUMN IF NOT EXISTS discount_code_id UUID
    REFERENCES ecommerce.discount_codes(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS idx_orders_discount_code_id
    ON ecommerce.orders(discount_code_id)
    WHERE discount_code_id IS NOT NULL;

-- DOWN
DROP INDEX IF EXISTS ecommerce.idx_orders_discount_code_id;
ALTER TABLE ecommerce.orders DROP COLUMN IF EXISTS discount_code_id;
