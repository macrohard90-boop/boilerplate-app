-- 044_fix_welcome_link_slash.sql
-- Add trailing slash to welcome_campaign link so Brevo redirect works correctly.
-- Bare origin URLs (http://host?params) fail in some redirect systems.

-- UP

UPDATE marketing.email_templates
SET html_content = replace(html_content, 'href="{{ frontend_url }}"', 'href="{{ frontend_url }}/"'),
    updated_at = NOW()
WHERE name = 'welcome_campaign'
  AND html_content LIKE '%href="{{ frontend_url }}"%';

-- DOWN

UPDATE marketing.email_templates
SET html_content = replace(html_content, 'href="{{ frontend_url }}/"', 'href="{{ frontend_url }}"'),
    updated_at = NOW()
WHERE name = 'welcome_campaign';
