"use client";

interface StarRatingProps {
  rating: number;
  size?: "sm" | "md" | "lg";
  interactive?: boolean;
  onChange?: (rating: number) => void;
}

export default function StarRating({
  rating,
  size = "md",
  interactive = false,
  onChange,
}: StarRatingProps) {
  const sizeMap = { sm: "w-3.5 h-3.5", md: "w-5 h-5", lg: "w-6 h-6" };
  const starSize = sizeMap[size];

  const stars = Array.from({ length: 5 }, (_, i) => {
    const filled = i + 1 <= Math.floor(rating);
    const half = !filled && i < rating;
    return { filled, half, index: i };
  });

  return (
    <div className="flex items-center gap-0.5">
      {stars.map(({ filled, half, index }) => (
        <button
          key={index}
          type="button"
          disabled={!interactive}
          onClick={() => interactive && onChange?.(index + 1)}
          className={`${interactive ? "cursor-pointer hover:scale-110" : "cursor-default"} transition-transform`}
        >
          <svg
            xmlns="http://www.w3.org/2000/svg"
            className={starSize}
            viewBox="0 0 24 24"
            fill={filled ? "#e0af68" : half ? "url(#half)" : "none"}
            stroke={filled || half ? "#e0af68" : "rgba(240,240,248,0.2)"}
            strokeWidth={1.5}
          >
            {half && (
              <defs>
                <linearGradient id="half">
                  <stop offset="50%" stopColor="#e0af68" />
                  <stop offset="50%" stopColor="transparent" />
                </linearGradient>
              </defs>
            )}
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M11.049 2.927c.3-.921 1.603-.921 1.902 0l1.519 4.674a1 1 0 00.95.69h4.915c.969 0 1.371 1.24.588 1.81l-3.976 2.888a1 1 0 00-.363 1.118l1.518 4.674c.3.922-.755 1.688-1.538 1.118l-3.976-2.888a1 1 0 00-1.176 0l-3.976 2.888c-.783.57-1.838-.197-1.538-1.118l1.518-4.674a1 1 0 00-.363-1.118l-3.976-2.888c-.784-.57-.38-1.81.588-1.81h4.914a1 1 0 00.951-.69l1.519-4.674z"
            />
          </svg>
        </button>
      ))}
    </div>
  );
}
