import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { serverFetch } from "../../../lib/server-fetch";
import ProductDetailClient, { type Product } from "./ProductDetailClient";

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

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const seoData = await serverFetch<SEOMetaResponse>(
    `/api/seo/meta/products/${slug}`
  );

  if (!seoData || !seoData.title) {
    return { title: "Product Not Found" };
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
      type: (["website", "article"].includes(seoData.og_tags["og:type"])
        ? seoData.og_tags["og:type"]
        : "website") as "website" | "article",
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

export default async function ProductPage({ params }: Props) {
  const { slug } = await params;

  // Fetch product and SEO data in parallel
  const [product, seoData] = await Promise.all([
    serverFetch<Product>(`/api/ecommerce/products/${slug}`),
    serverFetch<SEOMetaResponse>(`/api/seo/meta/products/${slug}`),
  ]);

  // If product doesn't exist or isn't active, show 404
  if (!product || product.status !== "active") {
    notFound();
  }

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
      <ProductDetailClient initialProduct={product} slug={slug} />
    </>
  );
}
