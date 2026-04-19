import Image from "next/image";
import Link from "next/link";
import { formatPrice } from "../lib/format";
import StarRating from "./StarRating";

const INTERVAL_LABELS: Record<string, string> = {
  day: "/day",
  week: "/wk",
  month: "/mo",
  year: "/yr",
};

interface ProductCardProps {
  slug: string;
  name: string;
  price: number; // cents
  currency?: string;
  image_url?: string | null;
  rating?: number;
  review_count?: number;
  category_name?: string;
  pricing_type?: string;
  recurring_interval?: string | null;
}

export default function ProductCard({
  slug,
  name,
  price,
  currency = "USD",
  image_url,
  rating,
  review_count,
  category_name,
  pricing_type,
  recurring_interval,
}: ProductCardProps) {
  return (
    <Link href={`/products/${slug}`} className="group block">
      <div className="glass rounded-xl overflow-hidden transition-all duration-300 group-hover:border-accent-purple/30 group-hover:shadow-lg group-hover:shadow-accent-purple/5">
        {/* Image */}
        <div className="aspect-square bg-base-100 relative overflow-hidden">
          {image_url ? (
            <Image
              src={image_url}
              alt={name}
              fill
              sizes="(max-width: 640px) 100vw, (max-width: 768px) 50vw, (max-width: 1024px) 33vw, 25vw"
              className="object-cover group-hover:scale-105 transition-transform duration-500"
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center text-text-muted">
              <svg
                xmlns="http://www.w3.org/2000/svg"
                className="h-12 w-12"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z"
                />
              </svg>
            </div>
          )}
        </div>

        {/* Info */}
        <div className="p-4">
          {category_name && (
            <span className="text-[10px] text-accent-purple font-medium uppercase tracking-wider">
              {category_name}
            </span>
          )}
          <h3 className="text-sm font-medium text-text-primary group-hover:text-accent-blue transition-colors truncate">
            {name}
          </h3>
          <div className="mt-2 flex items-center justify-between">
            <span className="text-lg font-semibold text-text-primary">
              {formatPrice(price, currency)}
              {pricing_type === "recurring" && recurring_interval && (
                <span className="text-sm font-normal text-text-muted">
                  {INTERVAL_LABELS[recurring_interval] ||
                    `/${recurring_interval}`}
                </span>
              )}
            </span>
            {rating !== undefined && (
              <div className="flex items-center gap-1">
                <StarRating rating={rating} size="sm" />
                {review_count !== undefined && (
                  <span className="text-xs text-text-muted">
                    ({review_count})
                  </span>
                )}
              </div>
            )}
          </div>
        </div>
      </div>
    </Link>
  );
}
