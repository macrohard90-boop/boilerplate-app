-- UP
-- 025: Email templates table + seed built-in templates
-- Enables DB-backed template CRUD for the marketing admin UI.
-- Hybrid resolution: DB templates take priority, filesystem fallback remains.

CREATE TABLE IF NOT EXISTS marketing.email_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(100) NOT NULL UNIQUE,
    display_name VARCHAR(255) NOT NULL,
    subject VARCHAR(500),
    html_content TEXT NOT NULL,
    category VARCHAR(50) NOT NULL DEFAULT 'campaign'
        CHECK (category IN ('transactional', 'campaign', 'automation')),
    description TEXT,
    variables JSONB NOT NULL DEFAULT '[]',
    is_builtin BOOLEAN NOT NULL DEFAULT false,
    version INT NOT NULL DEFAULT 1,
    created_by UUID REFERENCES core.users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_email_templates_category ON marketing.email_templates(category);
CREATE INDEX IF NOT EXISTS idx_email_templates_name ON marketing.email_templates(name);

-- Seed 8 built-in templates (content blocks only, base.html wrapping applied at render time)

INSERT INTO marketing.email_templates (name, display_name, subject, html_content, category, variables, is_builtin)
VALUES
(
    'welcome',
    'Welcome Email',
    'Welcome to {{ site_name }}',
    '<h2>Welcome, {{ first_name }}!</h2>
<p>Thank you for creating an account with {{ site_name }}. We''re glad to have you.</p>
{% if verify_url %}
<p>Please verify your email address by clicking the button below:</p>
<p style="text-align: center;">
  <a href="{{ verify_url }}" class="button">Verify Email Address</a>
</p>
<p class="muted">This link expires in 24 hours. If you didn''t create this account, you can safely ignore this email.</p>
<p class="muted">If the button doesn''t work, copy and paste this URL into your browser:<br>{{ verify_url }}</p>
{% endif %}',
    'transactional',
    '[{"name": "first_name", "description": "User''s first name"}, {"name": "verify_url", "description": "Email verification link (optional)"}]',
    true
),
(
    'password_reset',
    'Password Reset',
    'Reset your {{ site_name }} password',
    '<h2>Password Reset</h2>
<p>Hi {{ first_name }},</p>
<p>We received a request to reset your password. Click the button below to choose a new one:</p>
<p style="text-align: center;">
  <a href="{{ reset_url }}" class="button">Reset Password</a>
</p>
<p class="muted">This link expires in 1 hour. If you didn''t request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>
<p class="muted">If the button doesn''t work, copy and paste this URL into your browser:<br>{{ reset_url }}</p>',
    'transactional',
    '[{"name": "first_name", "description": "User''s first name"}, {"name": "reset_url", "description": "Password reset link"}]',
    true
),
(
    'order_confirmation',
    'Order Confirmation',
    'Order confirmed — {{ site_name }}',
    '<h2>Order Confirmed</h2>
<p>Hi {{ first_name }},</p>
<p>Your order <strong>#{{ order_id[:8] if order_id is string else order_id }}</strong> has been confirmed. Here''s a summary:</p>
{% if items %}
<table style="width: 100%; border-collapse: collapse; margin: 16px 0;">
  <thead>
    <tr style="border-bottom: 2px solid #eeeeee;">
      <th style="text-align: left; padding: 8px 0; color: #555;">Item</th>
      <th style="text-align: right; padding: 8px 0; color: #555;">Price</th>
    </tr>
  </thead>
  <tbody>
    {% for item in items %}
    <tr style="border-bottom: 1px solid #eeeeee;">
      <td style="padding: 8px 0;">{{ item.name }}{% if item.quantity > 1 %} x{{ item.quantity }}{% endif %}</td>
      <td style="text-align: right; padding: 8px 0;">{{ item.price }}</td>
    </tr>
    {% endfor %}
  </tbody>
  <tfoot>
    <tr>
      <td style="padding: 12px 0; font-weight: 600;">Total</td>
      <td style="text-align: right; padding: 12px 0; font-weight: 600;">{{ total }}</td>
    </tr>
  </tfoot>
</table>
{% endif %}
{% if order_url %}
<p style="text-align: center;">
  <a href="{{ order_url }}" class="button">View Order</a>
</p>
{% endif %}
<p class="muted">If you have any questions about your order, please contact our support team.</p>',
    'transactional',
    '[{"name": "first_name", "description": "User''s first name"}, {"name": "order_id", "description": "Order number or ID"}, {"name": "items", "description": "Array of {name, quantity, price}"}, {"name": "total", "description": "Formatted total amount"}, {"name": "order_url", "description": "Link to view order (optional)"}]',
    true
),
(
    'payment_receipt',
    'Payment Receipt',
    'Payment receipt — {{ site_name }}',
    '<h2>Payment Receipt</h2>
<p>Hi {{ first_name }},</p>
<p>We''ve received your payment. Here are the details:</p>
<table style="width: 100%; margin: 16px 0;">
  <tr>
    <td style="padding: 8px 0; color: #555;">Amount</td>
    <td style="text-align: right; padding: 8px 0; font-weight: 600;">{{ currency }} {{ amount }}</td>
  </tr>
  <tr>
    <td style="padding: 8px 0; color: #555;">Date</td>
    <td style="text-align: right; padding: 8px 0;">{{ date }}</td>
  </tr>
  {% if payment_method %}
  <tr>
    <td style="padding: 8px 0; color: #555;">Payment Method</td>
    <td style="text-align: right; padding: 8px 0;">{{ payment_method }}</td>
  </tr>
  {% endif %}
  {% if reference %}
  <tr>
    <td style="padding: 8px 0; color: #555;">Reference</td>
    <td style="text-align: right; padding: 8px 0;">{{ reference }}</td>
  </tr>
  {% endif %}
</table>
<p class="muted">This serves as your payment receipt. Please keep it for your records.</p>',
    'transactional',
    '[{"name": "first_name", "description": "User''s first name"}, {"name": "amount", "description": "Payment amount"}, {"name": "currency", "description": "Currency code"}, {"name": "date", "description": "Payment date"}, {"name": "payment_method", "description": "Payment method used (optional)"}, {"name": "reference", "description": "Payment reference ID (optional)"}]',
    true
),
(
    'subscription_confirmation',
    'Subscription Confirmed',
    'Subscription confirmed — {{ site_name }}',
    '<h2>Subscription Confirmed</h2>
<p>Hi {{ first_name }},</p>
<p>Your subscription to <strong>{{ plan_name }}</strong> is now active.</p>
{% if next_billing_date %}
<p>Your next billing date is <strong>{{ next_billing_date }}</strong>.</p>
{% endif %}
{% if dashboard_url %}
<p style="text-align: center;">
  <a href="{{ dashboard_url }}" class="button">Go to Dashboard</a>
</p>
{% endif %}
<p class="muted">You can manage your subscription at any time from your account settings.</p>',
    'transactional',
    '[{"name": "first_name", "description": "User''s first name"}, {"name": "plan_name", "description": "Subscription plan name"}, {"name": "next_billing_date", "description": "Next billing date (optional)"}, {"name": "dashboard_url", "description": "Dashboard link (optional)"}]',
    true
),
(
    'subscription_cancelled',
    'Subscription Cancelled',
    'Subscription cancelled — {{ site_name }}',
    '<h2>Subscription Cancelled</h2>
<p>Hi {{ first_name }},</p>
<p>Your subscription to <strong>{{ plan_name }}</strong> has been cancelled.</p>
{% if end_date %}
<p>You''ll continue to have access until <strong>{{ end_date }}</strong>.</p>
{% endif %}
<p>If this was a mistake or you''d like to resubscribe, you can do so from your account settings.</p>
{% if resubscribe_url %}
<p style="text-align: center;">
  <a href="{{ resubscribe_url }}" class="button">Resubscribe</a>
</p>
{% endif %}
<p class="muted">We''d love to have you back. If you have any feedback, please let us know.</p>',
    'transactional',
    '[{"name": "first_name", "description": "User''s first name"}, {"name": "plan_name", "description": "Subscription plan name"}, {"name": "end_date", "description": "Access end date (optional)"}, {"name": "resubscribe_url", "description": "Resubscribe link (optional)"}]',
    true
),
(
    'data_export_ready',
    'Data Export Ready',
    'Your data export is ready',
    '<h2>Your Data Export is Ready</h2>
<p>Hi {{ first_name }},</p>
<p>The data export you requested is now ready for download.</p>
<p style="text-align: center;">
  <a href="{{ download_url }}" class="button">Download Your Data</a>
</p>
{% if expires_at %}
<p class="muted">This download link will expire on {{ expires_at }}. Please download your data before then.</p>
{% endif %}
<p class="muted">This export contains all personal data we hold about your account, in compliance with data protection regulations.</p>',
    'transactional',
    '[{"name": "first_name", "description": "User''s first name"}, {"name": "download_url", "description": "Data download link"}, {"name": "expires_at", "description": "Link expiration date (optional)"}]',
    true
),
(
    'account_deletion',
    'Account Deletion',
    'Account deletion confirmation',
    '<h2>Account Deleted</h2>
<p>Hi {{ first_name }},</p>
<p>Your account and all associated personal data have been permanently deleted as of <strong>{{ deletion_date }}</strong>.</p>
<p>This action is irreversible. All your data has been removed from our systems in compliance with data protection regulations.</p>
<p class="muted">If you believe this was done in error, please contact our support team immediately.</p>',
    'transactional',
    '[{"name": "first_name", "description": "User''s first name"}, {"name": "deletion_date", "description": "Date account was deleted"}]',
    true
)
ON CONFLICT (name) DO NOTHING;

-- DOWN
DROP TABLE IF EXISTS marketing.email_templates CASCADE;
