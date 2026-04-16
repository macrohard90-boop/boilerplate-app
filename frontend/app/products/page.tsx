import type { Metadata } from "next";
import { serverFetch } from "../../lib/server-fetch";
import ProductsPageClient from "./ProductsPageClient";

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

export async function generateMetadata(): Promise<Metadata> {
  const seoData = await serverFetch<SEOMetaResponse>("/api/seo/meta/products");

  if (!seoData) {
    return {
      title: "Products",
      description: "Browse our full catalog.",
    };
  }

  const metadata: Metadata = {};

  if (seoData.title) metadata.title = seoData.title;
  if (seoData.description) metadata.description = seoData.description;
  if (seoData.robots) metadata.robots = seoData.robots;

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

export default async function ProductsPage() {
  const seoData = await serverFetch<SEOMetaResponse>("/api/seo/meta/products");

  return (
    <>
      {seoData?.structured_data?.map((sd, i) => (
        <script
          key={i}
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(sd) }}
        />
      ))}
      <ProductsPageClient />
    </>
  );
}
