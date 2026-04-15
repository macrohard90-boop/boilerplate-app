/**
 * Server-side fetch utility for Next.js server components.
 *
 * Uses INTERNAL_API_URL (container-to-container networking in Docker)
 * with ISR revalidation for caching.
 */

const INTERNAL_API_URL =
  process.env.INTERNAL_API_URL || "http://localhost:8000";

export async function serverFetch<T = unknown>(
  path: string,
  options?: { revalidate?: number }
): Promise<T | null> {
  const url = `${INTERNAL_API_URL}${path.startsWith("/") ? path : `/${path}`}`;
  try {
    const res = await fetch(url, {
      next: { revalidate: options?.revalidate ?? 60 },
    });
    if (!res.ok) return null;
    return res.json();
  } catch (error) {
    console.error(`Server fetch failed for ${path}:`, error);
    return null;
  }
}
