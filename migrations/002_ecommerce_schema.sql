-- Migration 002: E-commerce schema (21 tables — template choice: ecommerce)
-- Depends on: 001_core_schema.sql (references core.users)
-- Only runs when APP_TEMPLATE=ecommerce

-- UP

-- Categories (self-referencing hierarchy)
CREATE TABLE ecommerce.categories (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(200) NOT NULL,
    slug VARCHAR(200) NOT NULL UNIQUE,
    parent_id UUID REFERENCES ecommerce.categories(id) ON DELETE SET NULL,
    description TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_categories_slug ON ecommerce.categories(slug);
CREATE INDEX idx_categories_parent_id ON ecommerce.categories(parent_id);
CREATE INDEX idx_categories_created_at ON ecommerce.categories(created_at);

-- Products
CREATE TABLE ecommerce.products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(300) NOT NULL,
    slug VARCHAR(300) NOT NULL UNIQUE,
    description TEXT,
    sku VARCHAR(100) UNIQUE,
    base_price INTEGER NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    status VARCHAR(20) NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'active', 'archived')),
    type VARCHAR(20) NOT NULL DEFAULT 'physical' CHECK (type IN ('physical', 'digital')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ
);

CREATE INDEX idx_products_slug ON ecommerce.products(slug);
CREATE INDEX idx_products_sku ON ecommerce.products(sku);
CREATE INDEX idx_products_status ON ecommerce.products(status);
CREATE INDEX idx_products_type ON ecommerce.products(type);
CREATE INDEX idx_products_created_at ON ecommerce.products(created_at);
CREATE INDEX idx_products_deleted_at ON ecommerce.products(deleted_at) WHERE deleted_at IS NOT NULL;

CREATE TRIGGER set_updated_at BEFORE UPDATE ON ecommerce.products
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Product Categories (M2M junction)
CREATE TABLE ecommerce.product_categories (
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    category_id UUID NOT NULL REFERENCES ecommerce.categories(id) ON DELETE CASCADE,
    PRIMARY KEY (product_id, category_id)
);

CREATE INDEX idx_product_categories_category_id ON ecommerce.product_categories(category_id);

-- Product Variants
CREATE TABLE ecommerce.product_variants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    sku VARCHAR(100) UNIQUE,
    price_override INTEGER,
    stock_quantity INTEGER NOT NULL DEFAULT 0,
    attributes JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_product_variants_product_id ON ecommerce.product_variants(product_id);
CREATE INDEX idx_product_variants_sku ON ecommerce.product_variants(sku);
CREATE INDEX idx_product_variants_product_variant ON ecommerce.product_variants(product_id, id);
CREATE INDEX idx_product_variants_created_at ON ecommerce.product_variants(created_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON ecommerce.product_variants
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Product Images
CREATE TABLE ecommerce.product_images (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES ecommerce.product_variants(id) ON DELETE SET NULL,
    url TEXT NOT NULL,
    alt_text VARCHAR(500),
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_primary BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_product_images_product_id ON ecommerce.product_images(product_id);
CREATE INDEX idx_product_images_variant_id ON ecommerce.product_images(variant_id);

-- Product Reviews
CREATE TABLE ecommerce.product_reviews (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating >= 1 AND rating <= 5),
    title VARCHAR(200),
    body TEXT,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'approved', 'rejected')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_product_reviews_product_id ON ecommerce.product_reviews(product_id);
CREATE INDEX idx_product_reviews_user_id ON ecommerce.product_reviews(user_id);
CREATE INDEX idx_product_reviews_status ON ecommerce.product_reviews(status);
CREATE INDEX idx_product_reviews_created_at ON ecommerce.product_reviews(created_at);

-- Related Items
CREATE TABLE ecommerce.related_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    related_product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    relation_type VARCHAR(30) NOT NULL CHECK (relation_type IN ('cross-sell', 'upsell', 'project-link')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE(product_id, related_product_id, relation_type)
);

CREATE INDEX idx_related_items_product_id ON ecommerce.related_items(product_id);
CREATE INDEX idx_related_items_related_product_id ON ecommerce.related_items(related_product_id);

-- Inventory Records
CREATE TABLE ecommerce.inventory_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    variant_id UUID NOT NULL REFERENCES ecommerce.product_variants(id) ON DELETE CASCADE,
    quantity_change INTEGER NOT NULL,
    reason VARCHAR(100) NOT NULL,
    reference_id UUID,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_inventory_records_variant_id ON ecommerce.inventory_records(variant_id);
CREATE INDEX idx_inventory_records_created_at ON ecommerce.inventory_records(created_at);

-- Wishlists
CREATE TABLE ecommerce.wishlists (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL DEFAULT 'My Wishlist',
    is_default BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_wishlists_user_id ON ecommerce.wishlists(user_id);

-- Wishlist Items
CREATE TABLE ecommerce.wishlist_items (
    wishlist_id UUID NOT NULL REFERENCES ecommerce.wishlists(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES ecommerce.product_variants(id) ON DELETE SET NULL,
    added_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (wishlist_id, product_id)
);

CREATE INDEX idx_wishlist_items_product_id ON ecommerce.wishlist_items(product_id);

-- Discount Codes
CREATE TABLE ecommerce.discount_codes (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(50) NOT NULL UNIQUE,
    type VARCHAR(20) NOT NULL CHECK (type IN ('percentage', 'fixed', 'free_shipping')),
    value INTEGER NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    min_order_amount INTEGER NOT NULL DEFAULT 0,
    max_uses INTEGER,
    uses_count INTEGER NOT NULL DEFAULT 0,
    valid_from TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    valid_until TIMESTAMPTZ,
    active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_discount_codes_code ON ecommerce.discount_codes(code);
CREATE INDEX idx_discount_codes_active ON ecommerce.discount_codes(active);
CREATE INDEX idx_discount_codes_created_at ON ecommerce.discount_codes(created_at);

-- Digital Assets
CREATE TABLE ecommerce.digital_assets (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    file_url TEXT NOT NULL,
    file_name VARCHAR(255) NOT NULL,
    file_size BIGINT NOT NULL,
    download_limit INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_digital_assets_product_id ON ecommerce.digital_assets(product_id);

-- Pricing Tiers (volume discounts)
CREATE TABLE ecommerce.pricing_tiers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    variant_id UUID REFERENCES ecommerce.product_variants(id) ON DELETE CASCADE,
    min_quantity INTEGER NOT NULL,
    price_per_unit INTEGER NOT NULL,
    label VARCHAR(100),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_pricing_tiers_product_id ON ecommerce.pricing_tiers(product_id);
CREATE INDEX idx_pricing_tiers_variant_id ON ecommerce.pricing_tiers(variant_id);

-- Cart
CREATE TABLE ecommerce.cart (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES core.users(id) ON DELETE SET NULL,
    session_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'abandoned', 'recovered', 'converted', 'expired')),
    discount_code_id UUID REFERENCES ecommerce.discount_codes(id) ON DELETE SET NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_cart_user_id ON ecommerce.cart(user_id);
CREATE INDEX idx_cart_session_id ON ecommerce.cart(session_id);
CREATE INDEX idx_cart_status ON ecommerce.cart(status);
CREATE INDEX idx_cart_user_status ON ecommerce.cart(user_id, status);
CREATE INDEX idx_cart_created_at ON ecommerce.cart(created_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON ecommerce.cart
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Cart Items
CREATE TABLE ecommerce.cart_items (
    cart_id UUID NOT NULL REFERENCES ecommerce.cart(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    variant_id UUID NOT NULL REFERENCES ecommerce.product_variants(id) ON DELETE CASCADE,
    quantity INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price_at_add INTEGER NOT NULL,
    PRIMARY KEY (cart_id, product_id, variant_id)
);

CREATE INDEX idx_cart_items_product_id ON ecommerce.cart_items(product_id);
CREATE INDEX idx_cart_items_variant_id ON ecommerce.cart_items(variant_id);

-- Orders
CREATE TABLE ecommerce.orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE RESTRICT,
    order_number VARCHAR(50) NOT NULL UNIQUE,
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'accepted', 'completed', 'rejected', 'refunded')),
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    subtotal INTEGER NOT NULL,
    discount_amount INTEGER NOT NULL DEFAULT 0,
    tax_amount INTEGER NOT NULL DEFAULT 0,
    total INTEGER NOT NULL,
    shipping_address JSONB,
    billing_address JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_orders_user_id ON ecommerce.orders(user_id);
CREATE INDEX idx_orders_order_number ON ecommerce.orders(order_number);
CREATE INDEX idx_orders_status ON ecommerce.orders(status);
CREATE INDEX idx_orders_user_status ON ecommerce.orders(user_id, status);
CREATE INDEX idx_orders_created_at ON ecommerce.orders(created_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON ecommerce.orders
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Order Items
CREATE TABLE ecommerce.order_items (
    order_id UUID NOT NULL REFERENCES ecommerce.orders(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE RESTRICT,
    variant_id UUID NOT NULL REFERENCES ecommerce.product_variants(id) ON DELETE RESTRICT,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price INTEGER NOT NULL,
    total_price INTEGER NOT NULL,
    product_snapshot JSONB NOT NULL,
    PRIMARY KEY (order_id, product_id, variant_id)
);

CREATE INDEX idx_order_items_product_id ON ecommerce.order_items(product_id);
CREATE INDEX idx_order_items_variant_id ON ecommerce.order_items(variant_id);

-- Payment Records
CREATE TABLE ecommerce.payment_records (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    order_id UUID NOT NULL REFERENCES ecommerce.orders(id) ON DELETE RESTRICT,
    provider VARCHAR(50) NOT NULL,
    provider_payment_id VARCHAR(255),
    status VARCHAR(20) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'processing', 'succeeded', 'failed', 'refunded')),
    amount INTEGER NOT NULL,
    currency CHAR(3) NOT NULL DEFAULT 'USD',
    method VARCHAR(50),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_payment_records_order_id ON ecommerce.payment_records(order_id);
CREATE INDEX idx_payment_records_provider_payment_id ON ecommerce.payment_records(provider_payment_id);
CREATE INDEX idx_payment_records_status ON ecommerce.payment_records(status);
CREATE INDEX idx_payment_records_created_at ON ecommerce.payment_records(created_at);

-- Customer Metrics (RFM analysis)
CREATE TABLE ecommerce.customer_metrics (
    user_id UUID PRIMARY KEY REFERENCES core.users(id) ON DELETE CASCADE,
    last_purchase_at TIMESTAMPTZ,
    order_count INTEGER NOT NULL DEFAULT 0,
    total_spent INTEGER NOT NULL DEFAULT 0,
    default_currency CHAR(3) NOT NULL DEFAULT 'USD',
    rfm_segment VARCHAR(30) CHECK (rfm_segment IN (
        'champion', 'loyal', 'potential_loyalist', 'at_risk',
        'hibernating', 'lost', 'new'
    )),
    last_calculated_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_customer_metrics_rfm_segment ON ecommerce.customer_metrics(rfm_segment);
CREATE INDEX idx_customer_metrics_last_purchase_at ON ecommerce.customer_metrics(last_purchase_at);

CREATE TRIGGER set_updated_at BEFORE UPDATE ON ecommerce.customer_metrics
    FOR EACH ROW EXECUTE FUNCTION core.update_timestamp();

-- Abandoned Cart Events
CREATE TABLE ecommerce.abandoned_cart_events (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cart_id UUID NOT NULL REFERENCES ecommerce.cart(id) ON DELETE CASCADE,
    user_id UUID NOT NULL REFERENCES core.users(id) ON DELETE CASCADE,
    abandoned_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    reminder_count INTEGER NOT NULL DEFAULT 0,
    last_reminder_at TIMESTAMPTZ,
    recovered_at TIMESTAMPTZ,
    status VARCHAR(20) NOT NULL DEFAULT 'abandoned' CHECK (status IN ('abandoned', 'reminded', 'recovered', 'expired')),
    channel JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_abandoned_cart_user_id ON ecommerce.abandoned_cart_events(user_id);
CREATE INDEX idx_abandoned_cart_status ON ecommerce.abandoned_cart_events(status);
CREATE INDEX idx_abandoned_cart_abandoned_at ON ecommerce.abandoned_cart_events(abandoned_at);
CREATE INDEX idx_abandoned_cart_created_at ON ecommerce.abandoned_cart_events(created_at);

-- Product Associations (association rule learning)
CREATE TABLE ecommerce.product_associations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    product_a_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    product_b_id UUID NOT NULL REFERENCES ecommerce.products(id) ON DELETE CASCADE,
    rule_type VARCHAR(30) NOT NULL CHECK (rule_type IN ('frequently_bought_together', 'category_affinity', 'sequential')),
    support NUMERIC(8, 6) NOT NULL DEFAULT 0,
    confidence NUMERIC(8, 6) NOT NULL DEFAULT 0,
    lift NUMERIC(8, 4) NOT NULL DEFAULT 0,
    sample_size INTEGER NOT NULL DEFAULT 0,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE(product_a_id, product_b_id, rule_type)
);

CREATE INDEX idx_product_assoc_product_a ON ecommerce.product_associations(product_a_id);
CREATE INDEX idx_product_assoc_product_b ON ecommerce.product_associations(product_b_id);
CREATE INDEX idx_product_assoc_type_confidence ON ecommerce.product_associations(rule_type, confidence DESC);
CREATE INDEX idx_product_assoc_a_type ON ecommerce.product_associations(product_a_id, rule_type);

-- DOWN
DROP TABLE IF EXISTS ecommerce.product_associations CASCADE;
DROP TABLE IF EXISTS ecommerce.abandoned_cart_events CASCADE;
DROP TABLE IF EXISTS ecommerce.customer_metrics CASCADE;
DROP TABLE IF EXISTS ecommerce.payment_records CASCADE;
DROP TABLE IF EXISTS ecommerce.order_items CASCADE;
DROP TABLE IF EXISTS ecommerce.orders CASCADE;
DROP TABLE IF EXISTS ecommerce.cart_items CASCADE;
DROP TABLE IF EXISTS ecommerce.cart CASCADE;
DROP TABLE IF EXISTS ecommerce.pricing_tiers CASCADE;
DROP TABLE IF EXISTS ecommerce.digital_assets CASCADE;
DROP TABLE IF EXISTS ecommerce.discount_codes CASCADE;
DROP TABLE IF EXISTS ecommerce.wishlist_items CASCADE;
DROP TABLE IF EXISTS ecommerce.wishlists CASCADE;
DROP TABLE IF EXISTS ecommerce.inventory_records CASCADE;
DROP TABLE IF EXISTS ecommerce.related_items CASCADE;
DROP TABLE IF EXISTS ecommerce.product_reviews CASCADE;
DROP TABLE IF EXISTS ecommerce.product_images CASCADE;
DROP TABLE IF EXISTS ecommerce.product_variants CASCADE;
DROP TABLE IF EXISTS ecommerce.product_categories CASCADE;
DROP TABLE IF EXISTS ecommerce.products CASCADE;
DROP TABLE IF EXISTS ecommerce.categories CASCADE;
