-- 043_reseed_campaign_templates.sql
-- Re-insert campaign templates that were wiped by phase1_reset TRUNCATE CASCADE.
-- Root cause: TRUNCATE core.users CASCADE cascades to marketing.email_templates
-- via the created_by FK, wiping ALL templates. phase1_reset only re-seeded
-- transactional templates (025), not campaign templates (040).

-- UP

INSERT INTO marketing.email_templates (name, display_name, subject, html_content, category, description, variables, is_builtin, version)
VALUES

('winback', 'Win-Back', 'We miss you, {{ first_name }} — here''s 15% off', E'<h2>It''s been a while!</h2>\n<p>Hi {{ first_name }},</p>\n<p>We noticed you haven''t visited in a while, and we''d love to have you back. To make it easy, here''s an exclusive <strong>15% discount</strong> on your next order.</p>\n<p style="text-align: center; margin: 24px 0;">\n  <a href="{{ frontend_url }}/products?utm_source=email&utm_campaign=winback" class="button">Browse & Save 15%</a>\n</p>\n<p class="muted">Use code <strong>COMEBACK15</strong> at checkout. Offer valid for 7 days.</p>', 'campaign', 'Re-engage lapsed or at-risk users with a discount incentive', '[{"name": "first_name", "description": "Recipient first name"}]'::jsonb, true, 1),

('welcome_campaign', 'New Customer Welcome', 'Welcome aboard, {{ first_name }}!', E'<h2>Thanks for joining us!</h2>\n<p>Hi {{ first_name }},</p>\n<p>We''re thrilled to have you on board. There''s plenty to discover — take a look around and see what we have in store for you.</p>\n<p>If you have any questions, just reply to this email — we''re here to help.</p>\n<p style="text-align: center; margin: 24px 0;">\n  <a href="{{ frontend_url }}" class="button">Start Exploring</a>\n</p>', 'campaign', 'Welcome new signups or first-time buyers and guide them to explore', '[{"name": "first_name", "description": "Recipient first name"}]'::jsonb, true, 1),

('cart_abandonment', 'Cart Abandonment Nudge', 'You left something behind, {{ first_name }}', E'<h2>Still thinking it over?</h2>\n<p>Hi {{ first_name }},</p>\n<p>You left some items in your cart, and they''re waiting for you. Don''t miss out — stock can change at any time.</p>\n<p style="text-align: center; margin: 24px 0;">\n  <a href="{{ frontend_url }}/cart" class="button">Complete Your Order</a>\n</p>\n<p class="muted">Need help? Reply to this email and our team will assist you.</p>', 'campaign', 'Nudge users who abandoned their cart to complete the purchase', '[{"name": "first_name", "description": "Recipient first name"}]'::jsonb, true, 1),

('vip_thankyou', 'VIP Thank You', 'You''re one of our best customers, {{ first_name }}', E'<h2>A special thank you</h2>\n<p>Hi {{ first_name }},</p>\n<p>We wanted to take a moment to say <strong>thank you</strong>. You''re one of our most valued customers, and we truly appreciate your support.</p>\n<p>As a token of our gratitude, enjoy <strong>free shipping</strong> on your next order — no code needed, it''s already applied to your account.</p>\n<p style="text-align: center; margin: 24px 0;">\n  <a href="{{ frontend_url }}/products?utm_source=email&utm_campaign=vip" class="button">Shop Now</a>\n</p>\n<p class="muted">This is an exclusive perk for our top customers. Thank you for being part of our community.</p>', 'campaign', 'Thank high-value customers and reward them with a perk', '[{"name": "first_name", "description": "Recipient first name"}]'::jsonb, true, 1)

ON CONFLICT (name) DO UPDATE SET
  display_name = EXCLUDED.display_name,
  subject = EXCLUDED.subject,
  html_content = EXCLUDED.html_content,
  description = EXCLUDED.description,
  variables = EXCLUDED.variables,
  version = marketing.email_templates.version + 1,
  updated_at = NOW();

-- DOWN

DELETE FROM marketing.email_templates WHERE name IN ('winback', 'welcome_campaign', 'cart_abandonment', 'vip_thankyou');
