"use client";

import { Suspense, useEffect, useState, useCallback } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import ProductCard from "../../components/ProductCard";
import SearchBar from "../../components/SearchBar";
import Pagination from "../../components/Pagination";
import LoadingSpinner from "../../components/LoadingSpinner";

interface Product {
  id: string;
  name: string;
  slug: string;
  base_price: number;
  currency: string;
  description: string;
  pricing_type?: string;
  recurring_interval?: string | null;
  type?: string;
  images?: { url: string; is_primary: boolean }[];
  categories?: { name: string }[];
}

interface ProductResponse {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

const SORT_OPTIONS = [
  { value: "newest", label: "Newest" },
  { value: "price_asc", label: "Price: Low to High" },
  { value: "price_desc", label: "Price: High to Low" },
  { value: "name", label: "Name" },
];

const TABS = [
  { key: "one_time", label: "Products" },
  { key: "recurring", label: "Subscriptions" },
] as const;

type TabKey = (typeof TABS)[number]["key"];

function ProductsContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [data, setData] = useState<ProductResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState(searchParams.get("q") || "");
  const [sort, setSort] = useState(searchParams.get("sort") || "newest");
  const [page, setPage] = useState(Number(searchParams.get("page")) || 1);
  const [view, setView] = useState<"grid" | "list">("grid");
  const [tab, setTab] = useState<TabKey>(
    (searchParams.get("tab") as TabKey) || "one_time"
  );

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    params.set("page", String(page));
    params.set("page_size", "12");
    params.set("pricing_type", tab);
    params.set("status", "active");
    if (sort) params.set("sort", sort);
    if (search) params.set("q", search);

    try {
      const res = await fetch(`/api/ecommerce/products?${params}`);
      if (res.ok) {
        const json = await res.json();
        setData(json);
      }
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [page, sort, search, tab]);

  useEffect(() => {
    fetchProducts();
  }, [fetchProducts]);

  const handleSearch = useCallback((q: string) => {
    setSearch(q);
    setPage(1);
  }, []);

  const handleSort = (val: string) => {
    setSort(val);
    setPage(1);
  };

  const handleTab = (t: TabKey) => {
    setTab(t);
    setPage(1);
    setSearch("");
  };

  const activeTab = TABS.find((t) => t.key === tab)!;
  const isSubscriptions = tab === "recurring";

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-serif text-3xl sm:text-4xl font-bold mb-2">
          <span className="gradient-text">{activeTab.label}</span>
        </h1>
        <p className="text-text-secondary">
          {isSubscriptions
            ? "Plans and recurring subscriptions"
            : "Browse our full catalog"}
        </p>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-6 glass rounded-lg p-1 w-fit">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => handleTab(t.key)}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              tab === t.key
                ? "bg-accent-purple/20 text-accent-purple"
                : "text-text-muted hover:text-text-primary"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Controls */}
      <div className="flex flex-col sm:flex-row gap-4 mb-8">
        <SearchBar
          placeholder={isSubscriptions ? "Search subscriptions..." : "Search products..."}
          onSearch={handleSearch}
          className="flex-1"
        />
        <div className="flex items-center gap-3">
          <select
            value={sort}
            onChange={(e) => handleSort(e.target.value)}
            className="input-glass text-sm !w-auto !py-2"
          >
            {SORT_OPTIONS.map((o) => (
              <option key={o.value} value={o.value} className="bg-base text-text-primary">
                {o.label}
              </option>
            ))}
          </select>

          {/* View toggle */}
          <div className="flex glass rounded-lg overflow-hidden">
            <button
              onClick={() => setView("grid")}
              className={`p-2 transition-colors ${view === "grid" ? "bg-accent-purple/20 text-accent-purple" : "text-text-muted hover:text-text-primary"}`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
              </svg>
            </button>
            <button
              onClick={() => setView("list")}
              className={`p-2 transition-colors ${view === "list" ? "bg-accent-purple/20 text-accent-purple" : "text-text-muted hover:text-text-primary"}`}
            >
              <svg xmlns="http://www.w3.org/2000/svg" className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
              </svg>
            </button>
          </div>
        </div>
      </div>

      {/* Results */}
      {loading ? (
        <LoadingSpinner size="lg" className="py-20" />
      ) : !data || data.items.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-text-secondary text-lg">
            {isSubscriptions ? "No subscriptions found" : "No products found"}
          </p>
          {search && (
            <button onClick={() => handleSearch("")} className="btn-secondary text-sm mt-4">
              Clear search
            </button>
          )}
        </div>
      ) : (
        <>
          <p className="text-sm text-text-muted mb-6">
            {data.total} {isSubscriptions ? "plan" : "product"}{data.total !== 1 ? "s" : ""}
          </p>
          <div className={view === "grid"
            ? "grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6"
            : "space-y-4"
          }>
            {data.items.map((product) => (
              view === "grid" ? (
                <ProductCard
                  key={product.id}
                  slug={product.slug}
                  name={product.name}
                  price={product.base_price}
                  currency={product.currency}
                  image_url={product.images?.find((i) => i.is_primary)?.url || product.images?.[0]?.url}
                  category_name={product.categories?.[0]?.name}
                  pricing_type={product.pricing_type}
                  recurring_interval={product.recurring_interval}
                />
              ) : (
                <a key={product.id} href={`/products/${product.slug}`} className="glass rounded-xl p-4 flex gap-4 group hover:border-accent-purple/30 transition-all block">
                  <div className="w-20 h-20 bg-base-100 rounded-lg shrink-0 overflow-hidden">
                    {product.images?.[0] && (
                      <img src={product.images[0].url} alt={product.name} className="w-full h-full object-cover" />
                    )}
                  </div>
                  <div className="flex-1 min-w-0">
                    <h3 className="text-text-primary font-medium group-hover:text-accent-blue transition-colors">{product.name}</h3>
                    <p className="text-sm text-text-muted truncate mt-1">{product.description}</p>
                  </div>
                  <div className="text-lg font-semibold text-text-primary shrink-0">
                    {(product.base_price / 100).toLocaleString("en-US", { style: "currency", currency: product.currency })}
                    {product.pricing_type === "recurring" && product.recurring_interval && (
                      <span className="text-sm font-normal text-text-muted">
                        /{product.recurring_interval === "month" ? "mo" : product.recurring_interval === "year" ? "yr" : product.recurring_interval}
                      </span>
                    )}
                  </div>
                </a>
              )
            ))}
          </div>

          {data.total_pages > 1 && (
            <div className="mt-10">
              <Pagination
                currentPage={data.page}
                totalPages={data.total_pages}
                onPageChange={setPage}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}

export default function ProductsPage() {
  return (
    <Suspense fallback={<LoadingSpinner size="lg" className="py-40" />}>
      <ProductsContent />
    </Suspense>
  );
}
