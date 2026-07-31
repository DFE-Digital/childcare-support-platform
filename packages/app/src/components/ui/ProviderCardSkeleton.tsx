function formatDistance(miles: number): string {
  return miles >= 1 ? Math.round(miles).toString() : miles.toFixed(1);
}

interface ProviderCardSkeletonProps {
  distanceMiles: number;
  postcode?: string;
  onRetry?: () => void;
}

export function ProviderCardSkeleton({
  distanceMiles,
  postcode,
  onRetry,
}: ProviderCardSkeletonProps) {
  return (
    <div
      className="@container bg-white rounded-xl border border-zinc-200 p-5 cursor-pointer"
      role="option"
      aria-selected={false}
      aria-label={`Loading provider, ${formatDistance(distanceMiles)} miles${postcode ? ` from ${postcode}` : ""}`}
      onClick={onRetry}
    >
      <div className="animate-pulse">
        <div className="flex items-start justify-between gap-3">
          <div className="flex-1 min-w-0">
            <div className="h-5 bg-zinc-200 rounded w-3/5 mb-2" />
            <div className="flex gap-1.5 mb-2">
              <div className="h-5 bg-purple-100 rounded-full w-24" />
              <div className="h-5 bg-purple-100 rounded-full w-20" />
            </div>
            <div className="h-4 bg-zinc-100 rounded w-4/5" />
          </div>
          <div className="shrink-0 flex flex-col items-center gap-3">
            <div className="h-7 w-20 bg-zinc-100 rounded-full" />
            <div className="h-4 w-16 bg-zinc-100 rounded" />
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-x-4 gap-y-1 mt-2">
          <span className="inline-flex items-center gap-1 text-sm text-zinc-500">
            <i className="bi bi-geo" aria-hidden="true" />
            {formatDistance(distanceMiles)} miles
            {postcode && ` from ${postcode}`}
          </span>
          <div className="h-4 bg-zinc-100 rounded w-16" />
          <div className="h-4 bg-zinc-100 rounded w-20" />
          <div className="h-4 bg-zinc-100 rounded w-14" />
        </div>
      </div>
    </div>
  );
}
