"use client";

import { useState, useCallback, useEffect } from "react";
import Link from "next/link";
import ProductCard from "../../../components/ProductCard";
import Pagination from "../../../components/Pagination";

interface Category {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  parent_id: string | null;
  children?: Category[];
}

interface Product {
  id: string;
  name: string;
  slug: string;
  base_price: number;
  currency: string;
  images?: { url: string; is_primary: boolean }[];
}

interface ProductResponse {
  items: Product[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface Props {
  initialCategory: Category;
  initialProducts: ProductResponse | null;
}

export default function CategoryPageClient({
  initialCategory,
  initialProducts,
}: Props) {
  const category = initialCategory;
  const [products, setProducts] = useState<ProductResponse | null>(
    initialProducts
  );
  const [page, setPage] = useState(initialProducts?.page ?? 1);

  const fetchProducts = useCallback(
    async (pageNum: number) => {
      try {
        const res = await fetch(
          `/api/ecommerce/products?category_id=${category.id}&status=active&page=${pageNum}&page_size=12`
        );
        if (res.ok) {
          setProducts(await res.json());
        }
      } catch {}
    },
    [category.id]
  );

  // Re-fetch when page changes (but not on initial render with page 1)
  useEffect(() => {
    if (page !== (initialProducts?.page ?? 1)) {
      fetchProducts(page);
    }
  }, [page, fetchProducts, initialProducts?.page]);

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
        <span className="mx-2">/</span>
        <span className="text-text-secondary">{category.name}</span>
      </nav>

      {/* Header */}
      <div className="mb-10">
        <h1 className="font-serif text-3xl sm:text-4xl font-bold mb-2">
          <span className="gradient-text">{category.name}</span>
        </h1>
        {category.description && (
          <p className="text-text-secondary">{category.description}</p>
        )}
      </div>

      {/* Subcategories */}
      {category.children && category.children.length > 0 && (
        <div className="flex flex-wrap gap-3 mb-8">
          {category.children.map((sub) => (
            <Link
              key={sub.id}
              href={`/categories/${sub.slug}`}
              className="badge-purple text-sm"
            >
              {sub.name}
            </Link>
          ))}
        </div>
      )}

      {/* Products */}
      {!products || products.items.length === 0 ? (
        <div className="text-center py-20">
          <p className="text-text-secondary">
            No products in this category yet.
          </p>
        </div>
      ) : (
        <>
          <p className="text-sm text-text-muted mb-6">
            {products.total} product{products.total !== 1 ? "s" : ""}
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4 gap-6">
            {products.items.map((product) => (
              <ProductCard
                key={product.id}
                slug={product.slug}
                name={product.name}
                price={product.base_price}
                currency={product.currency}
                image_url={
                  product.images?.find((i) => i.is_primary)?.url ||
                  product.images?.[0]?.url
                }
              />
            ))}
          </div>

          {products.total_pages > 1 && (
            <div className="mt-10">
              <Pagination
                currentPage={products.page}
                totalPages={products.total_pages}
                onPageChange={setPage}
              />
            </div>
          )}
        </>
      )}
    </div>
  );
}
