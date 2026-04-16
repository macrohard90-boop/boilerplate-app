-- Migration 013: Stripe coupon sync fields on discount_codes
-- Enables syncing coupons to Stripe for use on subscriptions

-- UP

ALTER TABLE ecommerce.discount_codes
    ADD COLUMN stripe_coupon_id VARCHAR(255),
    ADD COLUMN stripe_promotion_code_id VARCHAR(255),
    ADD COLUMN applies_to VARCHAR(20) NOT NULL DEFAULT 'all'
        CHECK (applies_to IN ('all', 'one_time', 'recurring')),
    ADD COLUMN stripe_duration VARCHAR(20) NOT NULL DEFAULT 'once'
        CHECK (stripe_duration IN ('once', 'repeating', 'forever')),
    ADD COLUMN stripe_duration_in_months INTEGER;

CREATE INDEX idx_discount_codes_stripe_coupon_id ON ecommerce.discount_codes(stripe_coupon_id);


-- DOWN
ALTER TABLE ecommerce.discount_codes DROP COLUMN IF EXISTS stripe_duration_in_months;
ALTER TABLE ecommerce.discount_codes DROP COLUMN IF EXISTS stripe_duration;
ALTER TABLE ecommerce.discount_codes DROP COLUMN IF EXISTS applies_to;
ALTER TABLE ecommerce.discount_codes DROP COLUMN IF EXISTS stripe_promotion_code_id;
ALTER TABLE ecommerce.discount_codes DROP COLUMN IF EXISTS stripe_coupon_id;
