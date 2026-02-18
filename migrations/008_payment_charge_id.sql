-- Add charge_id column for tracking Stripe charge events (audit trail)
-- Also add 'expired' to payment_records status check constraint for stale order reaper

-- Add charge_id column
ALTER TABLE ecommerce.payment_records ADD COLUMN IF NOT EXISTS charge_id VARCHAR(255);

-- Update status check constraint to include 'expired'
ALTER TABLE ecommerce.payment_records DROP CONSTRAINT IF EXISTS payment_records_status_check;
ALTER TABLE ecommerce.payment_records ADD CONSTRAINT payment_records_status_check
    CHECK (status IN ('pending', 'processing', 'succeeded', 'failed', 'refunded', 'expired'));
