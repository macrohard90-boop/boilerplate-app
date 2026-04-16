import type { Metadata } from "next";
import { serverFetch } from "../../lib/server-fetch";

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
  const seoData = await serverFetch<SEOMetaResponse>("/api/seo/meta/about");

  if (!seoData) {
    return {
      title: "About",
      description: "Learn more about us.",
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

export default async function AboutPage() {
  const seoData = await serverFetch<SEOMetaResponse>("/api/seo/meta/about");

  return (
    <>
      {seoData?.structured_data?.map((sd, i) => (
        <script
          key={i}
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(sd) }}
        />
      ))}
      <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-16">
        <h1 className="font-serif text-3xl sm:text-4xl font-bold mb-6">
          <span className="gradient-text">About Us</span>
        </h1>

        <div className="space-y-6 text-text-secondary leading-relaxed">
          <p>
            Welcome to our store. We are passionate about delivering quality products
            and exceptional service to our customers.
          </p>

          <div className="glass rounded-xl p-6 space-y-4">
            <h2 className="text-xl font-semibold text-text-primary">
              Our Mission
            </h2>
            <p>
              We believe in making great products accessible to everyone. Our team
              works tirelessly to curate the best selection and provide a seamless
              shopping experience.
            </p>
          </div>

          <div className="glass rounded-xl p-6 space-y-4">
            <h2 className="text-xl font-semibold text-text-primary">
              What Sets Us Apart
            </h2>
            <ul className="list-disc list-inside space-y-2 text-text-secondary">
              <li>Carefully curated product selection</li>
              <li>Fast and reliable shipping</li>
              <li>Dedicated customer support</li>
              <li>Secure and easy checkout</li>
            </ul>
          </div>

          <div className="glass rounded-xl p-6 space-y-4">
            <h2 className="text-xl font-semibold text-text-primary">
              Get in Touch
            </h2>
            <p>
              Have questions or feedback? We&apos;d love to hear from you.
              Visit our{" "}
              <a href="/contact" className="text-accent-blue hover:text-accent-purple transition-colors">
                contact page
              </a>{" "}
              to reach out.
            </p>
          </div>
        </div>
      </div>
    </>
  );
}
