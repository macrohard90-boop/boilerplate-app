import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { serverFetch } from "../../../lib/server-fetch";
import CategoryPageClient from "./CategoryPageClient";

interface Category {
  id: string;
  name: string;
  slug: string;
  description: string | null;
  parent_id: string | null;
  children?: Category[];
}

interface ProductResponse {
  items: {
    id: string;
    name: string;
    slug: string;
    base_price: number;
    currency: string;
    images?: { url: string; is_primary: boolean }[];
  }[];
  total: number;
  page: number;
  page_size: number;
  total_pages: number;
}

interface SEOMetaResponse {
  path: string;
  title: string | null;
  description: string | null;
  canonical_url: string | null;
  robots: string;
  og_tags: Record<string, string> | null;
  twitter_tags: Record<string, string> | null;
  structured_data: Record<string, unknown>[] | null;
  is_custom: boolean;
}

interface Props {
  params: Promise<{ slug: string }>;
}

/** Recursively find a category by slug in the tree. */
function findCategory(cats: Category[], slug: string): Category | null {
  for (const c of cats) {
    if (c.slug === slug) return c;
    if (c.children) {
      const found = findCategory(c.children, slug);
      if (found) return found;
    }
  }
  return null;
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const seoData = await serverFetch<SEOMetaResponse>(
    `/api/seo/meta/categories/${slug}`,
  );

  if (!seoData || !seoData.title) {
    return { title: "Category Not Found" };
  }

  const metadata: Metadata = {
    title: seoData.title,
    description: seoData.description,
    robots: seoData.robots,
  };

  if (seoData.canonical_url) {
    metadata.alternates = { canonical: seoData.canonical_url };
  }

  if (seoData.og_tags) {
    metadata.openGraph = {
      title: seoData.og_tags["og:title"],
      description: seoData.og_tags["og:description"],
      url: seoData.og_tags["og:url"],
      siteName: seoData.og_tags["og:site_name"],
      images: seoData.og_tags["og:image"] ? [seoData.og_tags["og:image"]] : [],
      type: "website",
    };
  }

  if (seoData.twitter_tags) {
    metadata.twitter = {
      card:
        (seoData.twitter_tags["twitter:card"] as
          | "summary_large_image"
          | "summary") || "summary_large_image",
      title: seoData.twitter_tags["twitter:title"],
      description: seoData.twitter_tags["twitter:description"],
      site: seoData.twitter_tags["twitter:site"],
    };
  }

  return metadata;
}

export default async function CategoryPage({ params }: Props) {
  const { slug } = await params;

  // Fetch categories and SEO data in parallel
  const [allCategories, seoData] = await Promise.all([
    serverFetch<Category[]>("/api/ecommerce/categories"),
    serverFetch<SEOMetaResponse>(`/api/seo/meta/categories/${slug}`),
  ]);

  const category = allCategories ? findCategory(allCategories, slug) : null;

  if (!category) {
    notFound();
  }

  // Fetch initial products for the category
  const products = await serverFetch<ProductResponse>(
    `/api/ecommerce/products?category_id=${category.id}&status=active&page=1&page_size=12`,
  );

  return (
    <>
      {/* JSON-LD structured data */}
      {seoData?.structured_data?.map((sd, i) => (
        <script
          key={i}
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(sd) }}
        />
      ))}
      <CategoryPageClient
        initialCategory={category}
        initialProducts={products}
      />
    </>
  );
}
