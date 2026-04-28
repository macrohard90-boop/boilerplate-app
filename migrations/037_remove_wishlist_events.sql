-- 037: Remove wishlist & navigation event definitions, recategorize cookie_consent_given
-- Wishlist feature removed; nav_cart_clicked never fires; cookie_consent_given belongs in auth.

-- UP

-- Remove wishlist events (3)
DELETE FROM analytics.event_definitions WHERE name IN (
    'wishlist_removed',
    'wishlist_moved_to_cart',
    'empty_wishlist_viewed'
);

-- Remove nav_cart_clicked (redundant with cart events, never fires)
DELETE FROM analytics.event_definitions WHERE name = 'nav_cart_clicked';

-- Move cookie_consent_given from "navigation" to "auth"
UPDATE analytics.event_definitions SET category = 'auth' WHERE name = 'cookie_consent_given';

-- Clean up any historical wishlist events from the events table (optional, keeps data clean)
-- DELETE FROM analytics.events WHERE event_type IN ('wishlist_removed', 'wishlist_moved_to_cart', 'empty_wishlist_viewed', 'nav_cart_clicked');

-- DOWN
-- Re-insert wishlist events and restore cookie_consent_given category if needed
INSERT INTO analytics.event_definitions (name, description, category, payload_schema, source_locations, is_system) VALUES
('wishlist_removed', 'Fired when a user removes an item from their wishlist', 'wishlist', '[]', '[]', false),
('wishlist_moved_to_cart', 'Fired when a user moves a wishlist item to their cart', 'wishlist', '[]', '[]', false),
('empty_wishlist_viewed', 'Fired when a user views an empty wishlist page', 'wishlist', '[]', '[]', false)
ON CONFLICT (name) DO NOTHING;

UPDATE analytics.event_definitions SET category = 'navigation' WHERE name = 'cookie_consent_given';
