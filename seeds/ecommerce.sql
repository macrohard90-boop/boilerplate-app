-- E-commerce seed data
-- 5 categories (2 levels deep), 10 products with variants/images, discount codes, reviews

-- Categories (2 levels: 3 parents + 2 children)
INSERT INTO ecommerce.categories (id, name, slug, parent_id, description, sort_order) VALUES
    ('c0000000-0000-0000-0000-000000000001', 'Electronics', 'electronics', NULL, 'Electronic devices and accessories', 1),
    ('c0000000-0000-0000-0000-000000000002', 'Clothing', 'clothing', NULL, 'Apparel and fashion', 2),
    ('c0000000-0000-0000-0000-000000000003', 'Home & Garden', 'home-garden', NULL, 'Home improvement and garden supplies', 3),
    ('c0000000-0000-0000-0000-000000000004', 'Smartphones', 'smartphones', 'c0000000-0000-0000-0000-000000000001', 'Mobile phones and accessories', 1),
    ('c0000000-0000-0000-0000-000000000005', 'T-Shirts', 't-shirts', 'c0000000-0000-0000-0000-000000000002', 'Casual t-shirts', 1)
ON CONFLICT (slug) DO NOTHING;

-- Products (10 products, mix of physical and digital)
INSERT INTO ecommerce.products (id, name, slug, description, sku, base_price, currency, status, type) VALUES
    ('d0000000-0000-0000-0000-000000000001', 'Wireless Headphones', 'wireless-headphones', 'Premium noise-cancelling wireless headphones', 'WH-001', 7999, 'USD', 'active', 'physical'),
    ('d0000000-0000-0000-0000-000000000002', 'USB-C Hub', 'usb-c-hub', '7-in-1 USB-C hub with HDMI, USB 3.0, and SD card reader', 'UC-001', 4999, 'USD', 'active', 'physical'),
    ('d0000000-0000-0000-0000-000000000003', 'Classic T-Shirt', 'classic-tshirt', '100% cotton classic fit t-shirt', 'TS-001', 2499, 'USD', 'active', 'physical'),
    ('d0000000-0000-0000-0000-000000000004', 'Running Shoes', 'running-shoes', 'Lightweight running shoes with mesh upper', 'RS-001', 8999, 'USD', 'active', 'physical'),
    ('d0000000-0000-0000-0000-000000000005', 'Smart Watch', 'smart-watch', 'Fitness tracking smartwatch with heart rate monitor', 'SW-001', 19999, 'USD', 'active', 'physical'),
    ('d0000000-0000-0000-0000-000000000006', 'Plant Pot Set', 'plant-pot-set', 'Set of 3 ceramic plant pots', 'PP-001', 3499, 'USD', 'active', 'physical'),
    ('d0000000-0000-0000-0000-000000000007', 'E-Book: Web Dev Guide', 'ebook-web-dev', 'Complete guide to modern web development', 'EB-001', 1999, 'USD', 'active', 'digital'),
    ('d0000000-0000-0000-0000-000000000008', 'Desk Lamp', 'desk-lamp', 'LED desk lamp with adjustable brightness', 'DL-001', 4499, 'USD', 'active', 'physical'),
    ('d0000000-0000-0000-0000-000000000009', 'Backpack', 'backpack', 'Water-resistant laptop backpack 15.6 inch', 'BP-001', 5999, 'USD', 'active', 'physical'),
    ('d0000000-0000-0000-0000-000000000010', 'Coffee Mug', 'coffee-mug', 'Insulated stainless steel coffee mug 16oz', 'CM-001', 1499, 'USD', 'active', 'physical')
ON CONFLICT (slug) DO NOTHING;

-- Product-Category associations
INSERT INTO ecommerce.product_categories (product_id, category_id) VALUES
    ('d0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001'),
    ('d0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000001'),
    ('d0000000-0000-0000-0000-000000000003', 'c0000000-0000-0000-0000-000000000002'),
    ('d0000000-0000-0000-0000-000000000003', 'c0000000-0000-0000-0000-000000000005'),
    ('d0000000-0000-0000-0000-000000000004', 'c0000000-0000-0000-0000-000000000002'),
    ('d0000000-0000-0000-0000-000000000005', 'c0000000-0000-0000-0000-000000000001'),
    ('d0000000-0000-0000-0000-000000000005', 'c0000000-0000-0000-0000-000000000004'),
    ('d0000000-0000-0000-0000-000000000006', 'c0000000-0000-0000-0000-000000000003'),
    ('d0000000-0000-0000-0000-000000000008', 'c0000000-0000-0000-0000-000000000003'),
    ('d0000000-0000-0000-0000-000000000010', 'c0000000-0000-0000-0000-000000000003')
ON CONFLICT DO NOTHING;

-- Product Variants
INSERT INTO ecommerce.product_variants (id, product_id, name, sku, price_override, stock_quantity, attributes) VALUES
    -- Headphones: 2 colors
    ('e0000000-0000-0000-0000-000000000001', 'd0000000-0000-0000-0000-000000000001', 'Black', 'WH-001-BLK', NULL, 50, '{"color": "black"}'::jsonb),
    ('e0000000-0000-0000-0000-000000000002', 'd0000000-0000-0000-0000-000000000001', 'White', 'WH-001-WHT', NULL, 30, '{"color": "white"}'::jsonb),
    -- T-Shirt: 3 sizes
    ('e0000000-0000-0000-0000-000000000003', 'd0000000-0000-0000-0000-000000000003', 'Small', 'TS-001-S', NULL, 100, '{"size": "S", "color": "navy"}'::jsonb),
    ('e0000000-0000-0000-0000-000000000004', 'd0000000-0000-0000-0000-000000000003', 'Medium', 'TS-001-M', NULL, 150, '{"size": "M", "color": "navy"}'::jsonb),
    ('e0000000-0000-0000-0000-000000000005', 'd0000000-0000-0000-0000-000000000003', 'Large', 'TS-001-L', NULL, 120, '{"size": "L", "color": "navy"}'::jsonb),
    -- Running Shoes: 3 sizes
    ('e0000000-0000-0000-0000-000000000006', 'd0000000-0000-0000-0000-000000000004', 'Size 9', 'RS-001-9', NULL, 40, '{"size": "9"}'::jsonb),
    ('e0000000-0000-0000-0000-000000000007', 'd0000000-0000-0000-0000-000000000004', 'Size 10', 'RS-001-10', NULL, 60, '{"size": "10"}'::jsonb),
    ('e0000000-0000-0000-0000-000000000008', 'd0000000-0000-0000-0000-000000000004', 'Size 11', 'RS-001-11', NULL, 35, '{"size": "11"}'::jsonb),
    -- Smart Watch: 2 variants
    ('e0000000-0000-0000-0000-000000000009', 'd0000000-0000-0000-0000-000000000005', '42mm Silver', 'SW-001-42S', 19999, 25, '{"size": "42mm", "color": "silver"}'::jsonb),
    ('e0000000-0000-0000-0000-000000000010', 'd0000000-0000-0000-0000-000000000005', '46mm Black', 'SW-001-46B', 22999, 20, '{"size": "46mm", "color": "black"}'::jsonb),
    -- Single-variant products
    ('e0000000-0000-0000-0000-000000000011', 'd0000000-0000-0000-0000-000000000002', 'Default', 'UC-001-DEF', NULL, 200, '{}'::jsonb),
    ('e0000000-0000-0000-0000-000000000012', 'd0000000-0000-0000-0000-000000000006', 'Default', 'PP-001-DEF', NULL, 75, '{}'::jsonb),
    ('e0000000-0000-0000-0000-000000000013', 'd0000000-0000-0000-0000-000000000007', 'PDF', 'EB-001-PDF', NULL, 999, '{}'::jsonb),
    ('e0000000-0000-0000-0000-000000000014', 'd0000000-0000-0000-0000-000000000008', 'Default', 'DL-001-DEF', NULL, 80, '{}'::jsonb),
    ('e0000000-0000-0000-0000-000000000015', 'd0000000-0000-0000-0000-000000000009', 'Default', 'BP-001-DEF', NULL, 60, '{}'::jsonb),
    ('e0000000-0000-0000-0000-000000000016', 'd0000000-0000-0000-0000-000000000010', 'Default', 'CM-001-DEF', NULL, 300, '{}'::jsonb)
ON CONFLICT (sku) DO NOTHING;

-- Product Images
INSERT INTO ecommerce.product_images (product_id, variant_id, url, alt_text, sort_order, is_primary) VALUES
    ('d0000000-0000-0000-0000-000000000001', NULL, '/images/products/headphones-main.jpg', 'Wireless headphones front view', 1, TRUE),
    ('d0000000-0000-0000-0000-000000000002', NULL, '/images/products/usb-hub-main.jpg', 'USB-C Hub top view', 1, TRUE),
    ('d0000000-0000-0000-0000-000000000003', NULL, '/images/products/tshirt-main.jpg', 'Classic t-shirt flat lay', 1, TRUE),
    ('d0000000-0000-0000-0000-000000000004', NULL, '/images/products/shoes-main.jpg', 'Running shoes side view', 1, TRUE),
    ('d0000000-0000-0000-0000-000000000005', NULL, '/images/products/watch-main.jpg', 'Smart watch on wrist', 1, TRUE),
    ('d0000000-0000-0000-0000-000000000006', NULL, '/images/products/pots-main.jpg', 'Plant pot set arrangement', 1, TRUE),
    ('d0000000-0000-0000-0000-000000000007', NULL, '/images/products/ebook-cover.jpg', 'Web dev guide cover', 1, TRUE),
    ('d0000000-0000-0000-0000-000000000008', NULL, '/images/products/lamp-main.jpg', 'Desk lamp illuminated', 1, TRUE),
    ('d0000000-0000-0000-0000-000000000009', NULL, '/images/products/backpack-main.jpg', 'Backpack front view', 1, TRUE),
    ('d0000000-0000-0000-0000-000000000010', NULL, '/images/products/mug-main.jpg', 'Coffee mug with lid', 1, TRUE);

-- Discount Codes
INSERT INTO ecommerce.discount_codes (id, code, type, value, currency, min_order_amount, max_uses, active) VALUES
    ('f0000000-0000-0000-0000-000000000001', 'WELCOME10', 'percentage', 10, 'USD', 0, 1000, TRUE),
    ('f0000000-0000-0000-0000-000000000002', 'SAVE5', 'fixed', 500, 'USD', 2500, 500, TRUE),
    ('f0000000-0000-0000-0000-000000000003', 'FREESHIP', 'free_shipping', 0, 'USD', 5000, NULL, TRUE)
ON CONFLICT (code) DO NOTHING;

-- Product Reviews (from customer user)
INSERT INTO ecommerce.product_reviews (product_id, user_id, rating, title, body, status) VALUES
    ('d0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000003', 5, 'Amazing sound quality', 'Best headphones I have ever owned. The noise cancellation is incredible.', 'approved'),
    ('d0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002', 4, 'Great but pricey', 'Sound quality is excellent but a bit expensive for what you get.', 'approved'),
    ('d0000000-0000-0000-0000-000000000003', 'b0000000-0000-0000-0000-000000000003', 5, 'Perfect fit', 'Very comfortable and fits perfectly. Great quality cotton.', 'approved'),
    ('d0000000-0000-0000-0000-000000000005', 'b0000000-0000-0000-0000-000000000003', 4, 'Good fitness tracker', 'Tracks workouts well. Battery could be better.', 'approved'),
    ('d0000000-0000-0000-0000-000000000009', 'b0000000-0000-0000-0000-000000000003', 5, 'Holds everything', 'Fits my 15 inch laptop plus all accessories. Very durable.', 'approved');

-- Digital asset for e-book
INSERT INTO ecommerce.digital_assets (product_id, file_url, file_name, file_size, download_limit) VALUES
    ('d0000000-0000-0000-0000-000000000007', '/downloads/web-dev-guide.pdf', 'web-dev-guide.pdf', 15728640, 5);

-- Customer metrics for test customer
INSERT INTO ecommerce.customer_metrics (user_id, order_count, total_spent, default_currency) VALUES
    ('b0000000-0000-0000-0000-000000000003', 0, 0, 'USD')
ON CONFLICT (user_id) DO NOTHING;
