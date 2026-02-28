"use client";

import { useEffect, useState, useRef } from "react";
import Link from "next/link";
import ParticleCanvas from "../components/ParticleCanvas";
import ProductCard from "../components/ProductCard";

interface ProductImage {
  url: string;
  is_primary: boolean;
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
  base_price: number;
  currency: string;
  images?: ProductImage[];
  categories?: ProductCategory[];
}

interface Category {
  id: string;
  name: string;
  slug: string;
  description?: string;
  product_count?: number;
}

export default function HomePage() {
  const [products, setProducts] = useState<Product[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const revealRefs = useRef<HTMLDivElement[]>([]);

  useEffect(() => {
    fetch("/api/ecommerce/products?page_size=4&pricing_type=one_time")
      .then((r) => r.ok ? r.json() : { items: [] })
      .then((data) => setProducts(data.items || []))
      .catch(() => {});

    fetch("/api/ecommerce/categories")
      .then((r) => r.ok ? r.json() : [])
      .then((data) => setCategories(Array.isArray(data) ? data.slice(0, 4) : []))
      .catch(() => {});
  }, []);

  // Scroll reveal observer
  useEffect(() => {
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("visible");
          }
        });
      },
      { threshold: 0.1 }
    );

    revealRefs.current.forEach((el) => {
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [products, categories]);

  const addRevealRef = (el: HTMLDivElement | null) => {
    if (el && !revealRefs.current.includes(el)) {
      revealRefs.current.push(el);
    }
  };

  return (
    <>
      <ParticleCanvas />

      {/* Hero */}
      <section className="relative min-h-[90vh] flex items-center justify-center mesh-bg">
        <div className="relative z-10 text-center max-w-4xl mx-auto px-4">
          <h1 className="font-serif text-5xl sm:text-6xl md:text-7xl font-bold mb-6">
            <span className="gradient-text">Discover</span>
            <br />
            <span className="text-text-primary">What&apos;s Next</span>
          </h1>
          <p className="text-lg sm:text-xl text-text-secondary max-w-2xl mx-auto mb-10">
            A modern e-commerce experience with curated products, seamless checkout, and intelligent recommendations.
          </p>
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <Link href="/products" className="btn-primary text-base px-8 py-3">
              Browse Products
            </Link>
            <Link href="/auth/register" className="btn-gradient text-base px-8 py-3 text-text-primary">
              Get Started
            </Link>
          </div>
        </div>
      </section>

      {/* Featured Products */}
      {products.length > 0 && (
        <section className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div ref={addRevealRef} className="scroll-reveal">
            <h2 className="font-serif text-3xl sm:text-4xl font-bold text-center mb-3">
              <span className="gradient-text">Featured</span> Products
            </h2>
            <p className="text-center text-text-secondary mb-12">
              Hand-picked selections for you
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {products.map((product) => (
                <ProductCard
                  key={product.id}
                  slug={product.slug}
                  name={product.name}
                  price={product.base_price}
                  currency={product.currency}
                  image_url={product.images?.find((i) => i.is_primary)?.url || product.images?.[0]?.url}
                  category_name={product.categories?.[0]?.name}
                />
              ))}
            </div>
            <div className="text-center mt-10">
              <Link href="/products" className="btn-secondary text-sm">
                View All Products
              </Link>
            </div>
          </div>
        </section>
      )}

      {/* Categories */}
      {categories.length > 0 && (
        <section className="relative z-10 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
          <div ref={addRevealRef} className="scroll-reveal">
            <h2 className="font-serif text-3xl sm:text-4xl font-bold text-center mb-3">
              Shop by <span className="gradient-text">Category</span>
            </h2>
            <p className="text-center text-text-secondary mb-12">
              Find exactly what you&apos;re looking for
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
              {categories.map((cat) => (
                <Link key={cat.id} href={`/categories/${cat.slug}`} className="group">
                  <div className="glass rounded-xl p-6 text-center transition-all duration-300 group-hover:border-accent-blue/30 group-hover:shadow-lg group-hover:shadow-accent-blue/5">
                    <div className="w-14 h-14 mx-auto mb-4 rounded-full bg-gradient-to-br from-accent-purple/20 to-accent-blue/20 flex items-center justify-center">
                      <svg xmlns="http://www.w3.org/2000/svg" className="h-7 w-7 text-accent-blue" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                      </svg>
                    </div>
                    <h3 className="text-text-primary font-medium mb-1 group-hover:text-accent-blue transition-colors">
                      {cat.name}
                    </h3>
                    {cat.description && (
                      <p className="text-xs text-text-muted line-clamp-2">{cat.description}</p>
                    )}
                  </div>
                </Link>
              ))}
            </div>
          </div>
        </section>
      )}

      {/* CTA */}
      <section className="relative z-10 max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-20">
        <div ref={addRevealRef} className="scroll-reveal">
          <div className="glass rounded-2xl p-10 sm:p-16 text-center mesh-bg">
            <div className="relative z-10">
              <h2 className="font-serif text-3xl sm:text-4xl font-bold mb-4">
                Ready to <span className="gradient-text">get started</span>?
              </h2>
              <p className="text-text-secondary mb-8 max-w-lg mx-auto">
                Create your account today and explore our full catalog with personalized recommendations.
              </p>
              <Link href="/auth/register" className="btn-primary text-base px-10 py-3">
                Create Free Account
              </Link>
            </div>
          </div>
        </div>
      </section>
    </>
  );
}
