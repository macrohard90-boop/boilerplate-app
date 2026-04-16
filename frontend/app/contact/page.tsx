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
  const seoData = await serverFetch<SEOMetaResponse>("/api/seo/meta/contact");

  if (!seoData) {
    return {
      title: "Contact",
      description: "Get in touch with us.",
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

export default async function ContactPage() {
  const seoData = await serverFetch<SEOMetaResponse>("/api/seo/meta/contact");

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
          <span className="gradient-text">Contact Us</span>
        </h1>

        <p className="text-text-secondary mb-8 leading-relaxed">
          We&apos;d love to hear from you. Whether you have a question about our
          products, need help with an order, or just want to say hello — reach
          out using any of the methods below.
        </p>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
          <div className="glass rounded-xl p-6 space-y-3">
            <div className="w-10 h-10 rounded-lg bg-accent-blue/10 flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-accent-blue"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-text-primary">Email</h2>
            <p className="text-sm text-text-secondary">
              Send us an email and we&apos;ll get back to you within 24 hours.
            </p>
            <p className="text-sm text-accent-blue">support@example.com</p>
          </div>

          <div className="glass rounded-xl p-6 space-y-3">
            <div className="w-10 h-10 rounded-lg bg-accent-purple/10 flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-accent-purple"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
                />
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 11a3 3 0 11-6 0 3 3 0 016 0z"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-text-primary">Address</h2>
            <p className="text-sm text-text-secondary">
              Visit us at our office during business hours.
            </p>
            <p className="text-sm text-text-muted">
              123 Business Street
              <br />
              Suite 100
              <br />
              City, State 12345
            </p>
          </div>

          <div className="glass rounded-xl p-6 space-y-3">
            <div className="w-10 h-10 rounded-lg bg-accent-pink/10 flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-accent-pink"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M3 5a2 2 0 012-2h3.28a1 1 0 01.948.684l1.498 4.493a1 1 0 01-.502 1.21l-2.257 1.13a11.042 11.042 0 005.516 5.516l1.13-2.257a1 1 0 011.21-.502l4.493 1.498a1 1 0 01.684.949V19a2 2 0 01-2 2h-1C9.716 21 3 14.284 3 6V5z"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-text-primary">Phone</h2>
            <p className="text-sm text-text-secondary">
              Call us during business hours (Mon-Fri, 9AM-5PM).
            </p>
            <p className="text-sm text-accent-blue">+1 (555) 123-4567</p>
          </div>

          <div className="glass rounded-xl p-6 space-y-3">
            <div className="w-10 h-10 rounded-lg bg-green-500/10 flex items-center justify-center">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-5 w-5 text-green-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"
                />
              </svg>
            </div>
            <h2 className="text-lg font-semibold text-text-primary">
              Business Hours
            </h2>
            <p className="text-sm text-text-secondary">
              Our team is available during these hours.
            </p>
            <div className="text-sm text-text-muted space-y-1">
              <p>Monday - Friday: 9:00 AM - 5:00 PM</p>
              <p>Saturday - Sunday: Closed</p>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
