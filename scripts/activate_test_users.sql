-- Activate test users: verify emails, opt into marketing, set communication prefs.
-- Run on VM: psql $DATABASE_URL -f scripts/activate_test_users.sql

BEGIN;

-- 1. Verify all unverified users
UPDATE core.users
SET is_verified = TRUE
WHERE is_verified = FALSE AND is_active = TRUE;

-- 2. Ensure all active users have email_preferences with marketing_email = TRUE
INSERT INTO gdpr.email_preferences (user_id, marketing_email, transactional_email)
SELECT u.id, TRUE, TRUE
FROM core.users u
WHERE u.is_active = TRUE
  AND NOT EXISTS (
    SELECT 1 FROM gdpr.email_preferences ep WHERE ep.user_id = u.id
  );

-- Also flip existing users to marketing_email = TRUE
UPDATE gdpr.email_preferences
SET marketing_email = TRUE
WHERE user_id IN (SELECT id FROM core.users WHERE is_active = TRUE);

-- 3. Opt all active users into all enabled communication types
INSERT INTO marketing.user_communication_preferences (user_id, communication_type_id, allowed)
SELECT u.id, ct.id, TRUE
FROM core.users u
CROSS JOIN marketing.communication_types ct
WHERE u.is_active = TRUE AND ct.enabled = TRUE
ON CONFLICT (user_id, communication_type_id) DO UPDATE SET allowed = TRUE;

COMMIT;

-- Verify
SELECT u.email, u.is_verified, ep.marketing_email
FROM core.users u
LEFT JOIN gdpr.email_preferences ep ON ep.user_id = u.id
WHERE u.is_active = TRUE
ORDER BY u.created_at;
