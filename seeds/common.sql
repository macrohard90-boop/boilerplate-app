-- Common seed data: roles, permissions, and test users
-- Runs for both ecommerce and saas templates

-- Roles
INSERT INTO core.roles (id, name, description) VALUES
    ('a0000000-0000-0000-0000-000000000001', 'admin', 'Full system access'),
    ('a0000000-0000-0000-0000-000000000002', 'merchant', 'Product and order management'),
    ('a0000000-0000-0000-0000-000000000003', 'customer', 'Standard customer access')
ON CONFLICT (name) DO NOTHING;

-- Permissions (admin gets everything, merchant gets product/order, customer gets basic)
INSERT INTO core.permissions (role_id, resource, action) VALUES
    -- Admin permissions
    ('a0000000-0000-0000-0000-000000000001', 'users', 'read'),
    ('a0000000-0000-0000-0000-000000000001', 'users', 'write'),
    ('a0000000-0000-0000-0000-000000000001', 'users', 'delete'),
    ('a0000000-0000-0000-0000-000000000001', 'products', 'read'),
    ('a0000000-0000-0000-0000-000000000001', 'products', 'write'),
    ('a0000000-0000-0000-0000-000000000001', 'products', 'delete'),
    ('a0000000-0000-0000-0000-000000000001', 'orders', 'read'),
    ('a0000000-0000-0000-0000-000000000001', 'orders', 'write'),
    ('a0000000-0000-0000-0000-000000000001', 'analytics', 'read'),
    ('a0000000-0000-0000-0000-000000000001', 'settings', 'write'),
    -- Merchant permissions
    ('a0000000-0000-0000-0000-000000000002', 'products', 'read'),
    ('a0000000-0000-0000-0000-000000000002', 'products', 'write'),
    ('a0000000-0000-0000-0000-000000000002', 'orders', 'read'),
    ('a0000000-0000-0000-0000-000000000002', 'orders', 'write'),
    ('a0000000-0000-0000-0000-000000000002', 'analytics', 'read'),
    -- Customer permissions
    ('a0000000-0000-0000-0000-000000000003', 'products', 'read'),
    ('a0000000-0000-0000-0000-000000000003', 'orders', 'read')
ON CONFLICT (role_id, resource, action) DO NOTHING;

-- Test users (password: "Test1234!" hashed with bcrypt cost 12)
-- Hash: $2b$12$x/zScld/uyRyTNdtUhgeqOpu0nRcIn/2Bk6VU/cciUL97xyx47kP.
INSERT INTO core.users (id, email, password_hash, first_name, last_name, role_id, is_verified, is_active) VALUES
    ('b0000000-0000-0000-0000-000000000001', 'admin@example.com',
     '$2b$12$x/zScld/uyRyTNdtUhgeqOpu0nRcIn/2Bk6VU/cciUL97xyx47kP.',
     'Admin', 'User', 'a0000000-0000-0000-0000-000000000001', TRUE, TRUE),
    ('b0000000-0000-0000-0000-000000000002', 'merchant@example.com',
     '$2b$12$x/zScld/uyRyTNdtUhgeqOpu0nRcIn/2Bk6VU/cciUL97xyx47kP.',
     'Merchant', 'User', 'a0000000-0000-0000-0000-000000000002', TRUE, TRUE),
    ('b0000000-0000-0000-0000-000000000003', 'customer@example.com',
     '$2b$12$x/zScld/uyRyTNdtUhgeqOpu0nRcIn/2Bk6VU/cciUL97xyx47kP.',
     'Customer', 'User', 'a0000000-0000-0000-0000-000000000003', TRUE, TRUE)
ON CONFLICT (email) DO NOTHING;

-- Email preferences for test users (customer opts in to marketing)
INSERT INTO gdpr.email_preferences (user_id, marketing_email, transactional_email) VALUES
    ('b0000000-0000-0000-0000-000000000001', FALSE, TRUE),
    ('b0000000-0000-0000-0000-000000000002', FALSE, TRUE),
    ('b0000000-0000-0000-0000-000000000003', TRUE, TRUE)
ON CONFLICT (user_id) DO NOTHING;

-- Default exchange rate
INSERT INTO core.exchange_rates (base_currency, target_currency, rate, source) VALUES
    ('USD', 'EUR', 0.920000, 'manual'),
    ('USD', 'GBP', 0.790000, 'manual'),
    ('EUR', 'USD', 1.087000, 'manual'),
    ('GBP', 'USD', 1.265000, 'manual')
ON CONFLICT (base_currency, target_currency) DO NOTHING;
