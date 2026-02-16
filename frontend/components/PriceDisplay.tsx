import { formatPrice } from "../lib/format";

interface PriceDisplayProps {
  cents: number;
  currency?: string;
  className?: string;
  size?: "sm" | "md" | "lg";
}

export default function PriceDisplay({ cents, currency = "USD", className = "", size = "md" }: PriceDisplayProps) {
  const sizeClasses = {
    sm: "text-sm",
    md: "text-lg",
    lg: "text-2xl",
  };

  return (
    <span className={`font-semibold text-text-primary ${sizeClasses[size]} ${className}`}>
      {formatPrice(cents, currency)}
    </span>
  );
}
