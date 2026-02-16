"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import { formatPrice } from "../../../lib/format";
import { useCart } from "../../../lib/cart-context";
import { useToast } from "../../../components/Toast";
import StarRating from "../../../components/StarRating";
import LoadingSpinner from "../../../components/LoadingSpinner";

interface ProductImage {
  id: string;
  url: string;
  alt_text: string | null;
  is_primary: boolean;
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

interface Product {
  id: string;
  name: string;
  slug: string;
  description: string;
  sku: string;
  base_price: number;
  currency: string;
  status: string;
  type: string;
  images: ProductImage[];
  variants: ProductVariant[];
  categories: ProductCategory[];
}

interface Review {
  id: string;
  user_id: string;
  rating: number;
  title: string;
  comment: string;
  status: string;
  created_at: string;
}

export default function ProductDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const { addItem } = useCart();
  const { showToast } = useToast();
  const [product, setProduct] = useState<Product | null>(null);
  const [reviews, setReviews] = useState<Review[]>([]);
  const [loading, setLoading] = useState(true);
  const [selectedVariant, setSelectedVariant] = useState<ProductVariant | null>(null);
  const [selectedImage, setSelectedImage] = useState<string | null>(null);
  const [quantity, setQuantity] = useState(1);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      try {
        const res = await fetch(`/api/ecommerce/products/${slug}`);
        if (res.ok) {
          const data = await res.json();
          setProduct(data);
          if (data.variants?.length > 0) {
            setSelectedVariant(data.variants[0]);
          }
          const primary = data.images?.find((i: ProductImage) => i.is_primary);
          setSelectedImage(primary?.url || data.images?.[0]?.url || null);

          // Fetch reviews
          try {
            const revRes = await fetch(`/api/ecommerce/products/${data.id}/reviews`);
            if (revRes.ok) {
              const revData = await revRes.json();
              setReviews(revData.items || revData || []);
            }
          } catch {}
        }
      } catch {}
      setLoading(false);
    }
    if (slug) load();
  }, [slug]);

  if (loading) {
    return <LoadingSpinner size="lg" className="py-40" />;
  }

  if (!product) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-20 text-center">
        <h1 className="text-2xl font-semibold text-text-primary mb-4">Product Not Found</h1>
        <Link href="/products" className="btn-primary text-sm">Browse Products</Link>
      </div>
    );
  }

  const currentPrice = selectedVariant?.effective_price || product.base_price;
  const inStock = selectedVariant ? selectedVariant.stock_quantity > 0 : true;
  const avgRating = reviews.length > 0
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
        <Link href="/products" className="hover:text-text-secondary transition-colors">Products</Link>
        {product.categories?.[0] && (
          <>
            <span className="mx-2">/</span>
            <Link href={`/categories/${product.categories[0].slug}`} className="hover:text-text-secondary transition-colors">
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
          <div className="glass rounded-xl overflow-hidden aspect-square mb-4">
            {selectedImage ? (
              <img src={selectedImage} alt={product.name} className="w-full h-full object-cover" />
            ) : (
              <div className="w-full h-full flex items-center justify-center text-text-muted">
                <svg xmlns="http://www.w3.org/2000/svg" className="h-20 w-20" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
              </div>
            )}
          </div>
          {product.images.length > 1 && (
            <div className="flex gap-3 overflow-x-auto pb-2">
              {product.images.map((img) => (
                <button
                  key={img.id}
                  onClick={() => setSelectedImage(img.url)}
                  className={`w-16 h-16 rounded-lg overflow-hidden shrink-0 border-2 transition-all ${
                    selectedImage === img.url ? "border-accent-purple" : "border-transparent opacity-60 hover:opacity-100"
                  }`}
                >
                  <img src={img.url} alt={img.alt_text || ""} className="w-full h-full object-cover" />
                </button>
              ))}
            </div>
          )}
        </div>

        {/* Info */}
        <div>
          <h1 className="font-serif text-3xl font-bold text-text-primary mb-2">{product.name}</h1>

          {product.categories?.length > 0 && (
            <div className="flex gap-2 mb-4">
              {product.categories.map((cat) => (
                <Link key={cat.id} href={`/categories/${cat.slug}`} className="badge-purple text-xs">
                  {cat.name}
                </Link>
              ))}
            </div>
          )}

          {reviews.length > 0 && (
            <div className="flex items-center gap-2 mb-4">
              <StarRating rating={avgRating} size="sm" />
              <span className="text-sm text-text-secondary">
                {avgRating.toFixed(1)} ({reviews.length} review{reviews.length !== 1 ? "s" : ""})
              </span>
            </div>
          )}

          <div className="text-3xl font-bold gradient-text mb-6">
            {formatPrice(currentPrice, product.currency)}
          </div>

          <p className="text-text-secondary mb-8 leading-relaxed">{product.description}</p>

          {/* Variants */}
          {product.variants.length > 1 && (
            <div className="mb-6">
              <label className="block text-sm text-text-secondary mb-2">Variant</label>
              <div className="flex flex-wrap gap-2">
                {product.variants.map((v) => (
                  <button
                    key={v.id}
                    onClick={() => setSelectedVariant(v)}
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
              <span className="px-4 py-2 text-text-primary font-medium min-w-[40px] text-center">{quantity}</span>
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
              {adding ? "Adding..." : !inStock ? "Out of Stock" : "Add to Cart"}
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
          Reviews {reviews.length > 0 && <span className="text-text-muted font-normal text-lg">({reviews.length})</span>}
        </h2>

        {reviews.length === 0 ? (
          <div className="glass rounded-xl p-8 text-center">
            <p className="text-text-secondary">No reviews yet. Be the first to review this product.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {reviews.map((review) => (
              <div key={review.id} className="glass rounded-xl p-5">
                <div className="flex items-center gap-3 mb-2">
                  <StarRating rating={review.rating} size="sm" />
                  {review.title && (
                    <span className="text-sm font-medium text-text-primary">{review.title}</span>
                  )}
                </div>
                <p className="text-sm text-text-secondary">{review.comment}</p>
                <p className="text-xs text-text-muted mt-2">
                  {new Date(review.created_at).toLocaleDateString("en-US", { year: "numeric", month: "short", day: "numeric" })}
                </p>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
