import { useState } from "react";
import { PostcodeInput } from "@/components/ui/PostcodeInput";
import { usePostcodeLookup, type PostcodeGeo } from "@/hooks/usePostcodeLookup";
import { normalisePostcode, isPostcodeFormatValid } from "@/lib/postcode";

interface ProviderSearchProps {
  postcode: string;
  loading?: boolean;
  onPostcodeChange: (value: string) => void;
  onSearch: (postcode?: string, geo?: PostcodeGeo) => void;
}

export function ProviderSearch({
  postcode,
  loading,
  onPostcodeChange,
  onSearch,
}: ProviderSearchProps) {
  const { isValid, ensureInward } = usePostcodeLookup();
  const [error, setError] = useState(false);

  const handleSearch = async () => {
    const normalised = normalisePostcode(postcode);
    if (!isPostcodeFormatValid(normalised, true)) {
      setError(true);
      return;
    }
    const [outward] = normalised.split(" ");
    await ensureInward(outward);
    if (!isValid(normalised)) {
      setError(true);
      return;
    }
    onSearch();
  };

  const handleChange = (value: string) => {
    setError(false);
    onPostcodeChange(value);
  };

  const searchDisabled = loading || !postcode.trim();

  return (
    <div>
      <div className="flex items-end gap-2">
        <div className="flex-1 min-w-0">
          <PostcodeInput
            label="Search by postcode"
            value={postcode}
            error={error}
            onChange={handleChange}
            onSelect={(value, geo) => onSearch(value, geo)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !searchDisabled) {
                e.preventDefault();
                handleSearch();
              }
            }}
            aria-describedby={error ? "postcode-search-error" : undefined}
            aria-invalid={error || undefined}
          />
        </div>
        <button
          onClick={handleSearch}
          disabled={!!searchDisabled}
          className="btn-dark py-3 px-4 shrink-0"
          aria-label={loading ? "Searching" : undefined}
        >
          {loading ? (
            <>
              <div
                className="h-5 w-5 animate-spin rounded-full border-2 border-white border-t-transparent"
                aria-hidden="true"
              />
              <span className="sr-only">Searching</span>
            </>
          ) : (
            "Search"
          )}
        </button>
      </div>
      {error && (
        <p
          id="postcode-search-error"
          role="alert"
          className="text-base text-white bg-red-600 rounded-md px-4 py-2 inline-block mt-2"
        >
          Enter a valid UK postcode
        </p>
      )}
    </div>
  );
}
