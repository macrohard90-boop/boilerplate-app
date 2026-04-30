-- 042_welcome_template_single_cta.sql
-- Simplify welcome campaign template to a single "Start Exploring" CTA

-- UP

UPDATE marketing.email_templates
SET html_content = E'<h2>Thanks for joining us!</h2>\n<p>Hi {{ first_name }},</p>\n<p>We''re thrilled to have you on board. There''s plenty to discover — take a look around and see what we have in store for you.</p>\n<p>If you have any questions, just reply to this email — we''re here to help.</p>\n<p style="text-align: center; margin: 24px 0;">\n  <a href="{{ frontend_url }}" class="button">Start Exploring</a>\n</p>',
    updated_at = NOW()
WHERE name = 'welcome_campaign';

-- DOWN

UPDATE marketing.email_templates
SET html_content = E'<h2>Thanks for joining us!</h2>\n<p>Hi {{ first_name }},</p>\n<p>We''re thrilled to have you. Here are a few things you can do to get started:</p>\n<ul style="color: #555; line-height: 2;">\n  <li>Browse our <a href="{{ frontend_url }}/products" style="color: #2563eb;">latest products</a></li>\n  <li>Set up your <a href="{{ frontend_url }}/dashboard" style="color: #2563eb;">account preferences</a></li>\n  <li>Check out what''s trending this week</li>\n</ul>\n<p>If you have any questions, just reply to this email — we''re here to help.</p>\n<p style="text-align: center; margin: 24px 0;">\n  <a href="{{ frontend_url }}/products" class="button">Start Exploring</a>\n</p>',
    updated_at = NOW()
WHERE name = 'welcome_campaign';
