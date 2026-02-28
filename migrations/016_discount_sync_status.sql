-- Migration 016: Add Stripe sync status tracking to discount_codes
-- Matches the pattern used by products (migration 009)

ALTER TABLE ecommerce.discount_codes
    ADD COLUMN stripe_sync_status VARCHAR(20) NOT NULL DEFAULT 'unsynced'
        CHECK (stripe_sync_status IN ('unsynced', 'synced', 'error')),
    ADD COLUMN stripe_sync_error TEXT;

-- Backfill: if stripe_coupon_id exists, it was previously synced
UPDATE ecommerce.discount_codes
SET stripe_sync_status = 'synced'
WHERE stripe_coupon_id IS NOT NULL;

-- Free shipping discounts don't sync to Stripe — mark as synced
UPDATE ecommerce.discount_codes
SET stripe_sync_status = 'synced'
WHERE type = 'free_shipping';
