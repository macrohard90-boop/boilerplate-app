"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import Link from "next/link";
import { formatPrice } from "../../../lib/format";
import { useCart } from "../../../lib/cart-context";
import { useToast } from "../../../components/Toast";
import { trackEvent } from "../../../lib/track-event";
import StarRating from "../../../components/StarRating";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface ProductImage {
  id: string;
  url: string;
  alt_text: string | null;
  is_primary: boolean;
  variant_id: string | null;
}

interface ProductVariant {
  id: string;
  name: string;
  sku: string;
  price_override: number | null;
  stock_quantity: number;
  effective_price: number;
  attributes: Record<string, string>;
}

interface ProductCategory {
  id: string;
  name: string;
  slug: string;
}

export interface Product {
  id: string;
  name: string;
  slug: string;
  description: string;
  sku: string;
  base_price: number;
  currency: string;
  status: string;
  type: string;
  pricing_type?: string;
  recurring_interval?: string | null;
  recurring_interval_count?: number;
  trial_period_days?: number | null;
  images: ProductImage[];
  variants: ProductVariant[];
  categories: ProductCategory[];
}

const INTERVAL_LABELS: Record<string, string> = {
  day: "daily",
  week: "weekly",
  month: "monthly",
  year: "yearly",
};

const INTERVAL_SHORT: Record<string, string> = {
  day: "/day",
  week: "/wk",
  month: "/mo",
  year: "/yr",
};

interface Review {
  id: string;
  user_id: string;
  rating: number;
  title: string;
  comment: string;
  status: string;
  created_at: string;
}

interface Props {
  initialProduct: Product | null;
  slug: string;
}

export default function ProductDetailClient({ initialProduct, slug }: Props) {
  const { addItem } = useCart();
  const { showToast } = useToast();
  const [product, setProduct] = useState<Product | null>(initialProduct);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(!initialProduct);
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(
    initialProduct?.variants?.[0] ?? null,
  );
  const [selectedImage, setSelectedImage] = useState<string | null>(() => {
    if (!initialProduct) return null;
    const primary = initialProduct.images?.find((i) => i.is_primary);
    return primary?.url || initialProduct.images?.[0]?.url || null;
  });
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    async function load() {
      // If no initial product (fallback for client nav), fetch it
      if (!initialProduct) {
        setLoading(true);
        try {
          const res = await fetch(`/api/ecommerce/products/${slug}`);
          if (res.ok) {
            const data = await res.json();
            if (data.status !== "active") {
              setProduct(null);
              setLoading(false);
              return;
            }
            setProduct(data);
            if (data.variants?.length > 0) {
              setSelectedVariant(data.variants[0]);
            }
            const primary = data.images?.find(
              (i: ProductImage) => i.is_primary,
            );
            setSelectedImage(primary?.url || data.images?.[0]?.url || null);
          }
        } catch {}
        setLoading(false);
      }

      // Fetch reviews (always client-side, not SEO-critical)
      const productData = initialProduct || product;
      if (productData) {
        try {
          const revRes = await fetch(
            `/api/ecommerce/products/${productData.id}/reviews`,
          );
          if (revRes.ok) {
            const revData = await revRes.json();
            setReviews(revData.items || revData || []);
          }
        } catch {}
      }
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  // Track product view
  useEffect(() => {
    const p = initialProduct || product;
    if (!p) return;
    trackEvent("product_viewed", {
      product_id: p.id,
      slug: p.slug,
      name: p.name,
      price: p.base_price,
      category: p.categories?.[0]?.name,
    });
    const variant = p.variants?.[0];
    if (variant && variant.stock_quantity === 0) {
      trackEvent("out_of_stock_viewed", {
        product_id: p.id,
        name: p.name,
        category: p.categories?.[0]?.name,
      });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [slug]);

  // Swap gallery when variant changes
  useEffect(() => {
    if (!product) return;
    const variantImages = selectedVariant
      ? product.images.filter((i) => i.variant_id === selectedVariant.id)
      : [];
    const displayImages =
      variantImages.length > 0
        ? variantImages
        : product.images.filter((i) => !i.variant_id);
    const primary = displayImages.find((i) => i.is_primary);
    setSelectedImage(primary?.url || displayImages[0]?.url || null);
  }, [selectedVariant, product]);

  if (loading) {
    return <LoadingSpinner size="lg" className="py-40" />;
  }

  if (!product) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <h1 className="text-2xl font-semibold text-text-primary mb-4">
          Product Not Found
        </h1>
        <Link href="/products" className="btn-primary text-sm">
          Browse Products
        </Link>
      </div>
    );
  }

  const variantImgs = selectedVariant
    ? product.images.filter((i) => i.variant_id === selectedVariant.id)
    : [];
  const displayImages =
    variantImgs.length > 0
      ? variantImgs
      : product.images.filter((i) => !i.variant_id);

  const currentPrice = selectedVariant?.effective_price || product.base_price;
  const inStock = selectedVariant ? selectedVariant.stock_quantity > 0 : true;
  const avgRating =
    reviews.length > 0
      ? reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length
      : 0;

  async function handleAddToCart() {
    if (!product) return;
    setAdding(true);
    try {
      await addItem(product.id, selectedVariant?.id, quantity);
      showToast(`${product.name} added to cart`, "success");
    } catch {
      showToast("Failed to add to cart", "error");
    }
    setAdding(false);
  }

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Breadcrumb */}
      <nav className="mb-6 text-sm text-text-muted">
        <Link
          href="/products"
          className="hover:text-text-secondary transition-colors"
        >
          Products
        </Link>
        {product.categories?.[0] && (
          <>
            <span className="mx-2">/</span>
            <Link
              href={`/categories/${product.categories[0].slug}`}
              className="hover:text-text-secondary transition-colors"
            >
              {product.categories[0].name}
            </Link>
          </>
        )}
        <span className="mx-2">/</span>
        <span className="text-text-secondary">{product.name}</span>
      </nav>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-10">
        {/* Images */}
        <div>
          <div className="glass rounded-xl overflow-hidden aspect-square mb-4 relative">
            {selectedImage ? (
              <Image
                src={selectedImage}
                alt={product.name}
                fill
                sizes="(max-width: 1024px) 100vw, 50vw"
                className="object-cover"
                priority
              />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-text-muted">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-20 w-20"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={1}
                    d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                  />
                </svg>
              </div>
            )}
          </div>
          {displayImages.length > 1 && (
            <div className="flex gap-3 overflow-x-auto pb-2">
              {displayImages.map((img) => (
                <button
                  key={img.id}
                  onClick={() => setSelectedImage(img.url)}
                  className={`w-16 h-16 rounded-lg overflow-hidden shrink-0 border-2 transition-all relative ${
                    selectedImage === img.url
                      ? "border-accent-purple"
                      : "border-transparent opacity-60 hover:opacity-100"
                  }`}
                >
                  <Image
                    src={img.url}
                    alt={img.alt_text || ""}
                    fill
                    sizes="64px"
                    className="object-cover"
                  />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Info */}
        <div>
          <h1 className="font-serif text-3xl font-bold text-text-primary mb-2">
            {product.name}
          </h1>

          {product.categories?.length > 0 && (
            <div className="flex gap-2 mb-4">
              {product.categories.map((cat) => (
                <Link
                  key={cat.id}
                  href={`/categories/${cat.slug}`}
                  className="badge-purple text-xs"
                >
                  {cat.name}
                </Link>
              ))}
            </div>
          )}

          {reviews.length > 0 && (
            <div className="flex items-center gap-2 mb-4">
              <StarRating rating={avgRating} size="sm" />
              <span className="text-sm text-text-secondary">
                {avgRating.toFixed(1)} ({reviews.length} review
                {reviews.length !== 1 ? "s" : ""})
              </span>
            </div>
          )}

          <div className="text-3xl font-bold gradient-text mb-2">
            {formatPrice(currentPrice, product.currency)}
            {product.pricing_type === "recurring" &&
              product.recurring_interval && (
                <span className="text-lg font-normal text-text-muted">
                  {INTERVAL_SHORT[product.recurring_interval] ||
                    `/${product.recurring_interval}`}
                </span>
              )}
          </div>

          {product.pricing_type === "recurring" && (
            <div className="flex flex-wrap gap-2 mb-4">
              {product.recurring_interval && (
                <span className="text-sm text-text-secondary">
                  Billed{" "}
                  {product.recurring_interval_count &&
                  product.recurring_interval_count > 1
                    ? `every ${product.recurring_interval_count} ${product.recurring_interval}s`
                    : INTERVAL_LABELS[product.recurring_interval] ||
                      product.recurring_interval}
                </span>
              )}
              {product.trial_period_days && product.trial_period_days > 0 && (
                <span className="text-sm text-accent-blue font-medium ml-2">
                  {product.trial_period_days}-day free trial
                </span>
              )}
            </div>
          )}

          <p className="text-text-secondary mb-8 leading-relaxed">
            {product.description}
          </p>

          {/* Variants */}
          {product.variants.length > 1 && (
            <div className="mb-6">
              <label className="block text-sm text-text-secondary mb-2">
                Variant
              </label>
              <div className="flex flex-wrap gap-2">
                {product.variants.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => {
                      setSelectedVariant(v);
                      trackEvent("variant_selected", {
                        product_id: product.id,
                        variant_id: v.id,
                        variant_name: v.name,
                      });
                    }}
                    className={`px-4 py-2 rounded-lg text-sm transition-all ${
                      selectedVariant?.id === v.id
                        ? "bg-accent-purple/20 border border-accent-purple/40 text-accent-purple"
                        : "glass text-text-secondary hover:text-text-primary"
                    } ${v.stock_quantity === 0 ? "opacity-40 line-through" : ""}`}
                    disabled={v.stock_quantity === 0}
                  >
                    {v.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Quantity + Add to Cart */}
          <div className="flex items-center gap-4 mb-6">
            <div className="flex items-center glass rounded-lg">
              <button
                onClick={() => setQuantity(Math.max(1, quantity - 1))}
                className="px-3 py-2 text-text-secondary hover:text-text-primary transition-colors"
              >
                -
              </button>
              <span className="px-4 py-2 text-text-primary font-medium min-w-[40px] text-center">
                {quantity}
              </span>
              <button
                onClick={() => setQuantity(quantity + 1)}
                className="px-3 py-2 text-text-secondary hover:text-text-primary transition-colors"
              >
                +
              </button>
            </div>
            <button
              onClick={handleAddToCart}
              disabled={!inStock || adding}
              className="btn-primary flex-1 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {adding
                ? "Adding..."
                : !inStock
                  ? "Out of Stock"
                  : product.pricing_type === "recurring"
                    ? "Subscribe"
                    : "Add to Cart"}
            </button>
          </div>

          {/* SKU */}
          <p className="text-xs text-text-muted">
            SKU: {selectedVariant?.sku || product.sku}
          </p>
        </div>
      </div>

      {/* Reviews */}
      <section className="mt-16">
        <h2 className="font-serif text-2xl font-bold text-text-primary mb-6">
          Reviews{" "}
          {reviews.length > 0 && (
            <span className="text-text-muted font-normal text-lg">
              ({reviews.length})
            </span>
          )}
        </h2>

        {reviews.length === 0 ? (
          <div className="glass rounded-xl p-8 text-center">
            <p className="text-text-secondary">
              No reviews yet. Be the first to review this product.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {reviews.map((review) => (
              <div key={review.id} className="glass rounded-xl p-5">
                <div className="flex items-center gap-3 mb-2">
                  <StarRating rating={review.rating} size="sm" />
                  {review.title && (
                    <span className="text-sm font-medium text-text-primary">
                      {review.title}
                    </span>
                  )}
                </div>
                <p className="text-sm text-text-secondary">{review.comment}</p>
                <p className="text-xs text-text-muted mt-2">
                  {new Date(review.created_at).toLocaleDateString("en-US", {
                    year: "numeric",
                    month: "short",
                    day: "numeric",
                  })}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
