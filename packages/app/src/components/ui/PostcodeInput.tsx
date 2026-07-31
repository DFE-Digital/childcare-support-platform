import {
  useState,
  useRef,
  useEffect,
  useCallback,
  useMemo,
  useId,
} from "react";
import { TextInput } from "./TextInput";
import { usePostcodeLookup, type PostcodeGeo } from "@/hooks/usePostcodeLookup";
import { isPostcodeFormatValid, isCrownDependency } from "@/lib/postcode";

interface PostcodeInputProps {
  label?: string;
  value: string;
  error?: boolean;
  onChange: (value: string) => void;
  onSelect?: (postcode: string, geo: PostcodeGeo) => void;
  onKeyDown?: (e: React.KeyboardEvent<HTMLInputElement>) => void;
  onValidate?: (valid: boolean) => void;
  "aria-describedby"?: string;
  "aria-invalid"?: boolean;
}

const MAX_SUGGESTIONS = 20;

export function PostcodeInput({
  label,
  value,
  error,
  onChange,
  onSelect,
  onKeyDown,
  onValidate,
  "aria-describedby": ariaDescribedBy,
  "aria-invalid": ariaInvalid,
}: PostcodeInputProps) {
  const [open, setOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState(-1);
  const containerRef = useRef<HTMLDivElement>(null);
  const listboxId = useId();

  const {
    filterOutward,
    filterInward,
    getGeo,
    prefetchInward,
    isLoading,
    outwardLoaded,
  } = usePostcodeLookup();

  // Parse input into outward/inward parts
  const parsed = useMemo(() => {
    const trimmed = value.trimStart().toUpperCase();
    const spaceIdx = trimmed.indexOf(" ");
    if (spaceIdx > 0) {
      return {
        outward: trimmed.slice(0, spaceIdx),
        inward: trimmed.slice(spaceIdx + 1),
        phase: "inward" as const,
      };
    }
    // No space — if long enough, split last 3 chars as inward (standard UK format)
    if (trimmed.length > 3) {
      const outward = trimmed.slice(0, -3);
      const inward = trimmed.slice(-3);
      // Only auto-split if the derived outward looks plausible (starts with a letter)
      // and inward starts with a digit — prevents false splits on partial input
      if (
        /^[A-Z]/.test(outward) &&
        /^\d/.test(inward) &&
        filterOutward(outward).includes(outward)
      ) {
        return { outward, inward, phase: "inward" as const };
      }
    }
    return { outward: trimmed, inward: "", phase: "outward" as const };
  }, [value, filterOutward]);

  const outwardInvalid = useMemo(() => {
    if (!outwardLoaded || !parsed.outward) return false;
    if (isCrownDependency(parsed.outward)) return false;
    return filterOutward(parsed.outward).length === 0;
  }, [outwardLoaded, parsed.outward, filterOutward]);

  const formatInvalid = useMemo(() => {
    const trimmed = value.trim();
    if (!trimmed) return false;
    return !isPostcodeFormatValid(trimmed);
  }, [value]);

  // Build suggestions based on phase
  const suggestions = useMemo(() => {
    if (parsed.phase === "outward") {
      const matches = filterOutward(parsed.outward);
      // If exact single match, switch to inward prefetch
      if (matches.length === 1 && matches[0] === parsed.outward) {
        prefetchInward(parsed.outward);
        return [];
      }
      return matches.slice(0, MAX_SUGGESTIONS).map((code) => ({
        label: code,
        value: code + " ",
        isOutward: true,
      }));
    }
    // Inward phase
    const matches = filterInward(parsed.outward, parsed.inward);
    return matches.slice(0, MAX_SUGGESTIONS).map((inward) => ({
      label: `${parsed.outward} ${inward}`,
      value: `${parsed.outward} ${inward}`,
      isOutward: false,
    }));
  }, [parsed, filterOutward, filterInward, prefetchInward]);

  const showSuggestions = open && suggestions.length > 0;
  const showLoadingHint =
    open && parsed.phase === "inward" && suggestions.length === 0 && isLoading;

  // Reset active index when value changes
  const [prevValue, setPrevValue] = useState(value);
  if (value !== prevValue) {
    setPrevValue(value);
    setActiveIndex(-1);
  }

  // Prefetch inward data when outward code is complete
  useEffect(() => {
    if (parsed.phase === "inward" && parsed.outward) {
      prefetchInward(parsed.outward);
    }
  }, [parsed.phase, parsed.outward, prefetchInward]);

  const handleClickOutside = useCallback((e: MouseEvent) => {
    if (
      containerRef.current &&
      !containerRef.current.contains(e.target as Node)
    ) {
      setOpen(false);
    }
  }, []);

  useEffect(() => {
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [handleClickOutside]);

  function select(item: (typeof suggestions)[0]) {
    onChange(item.value);
    if (item.isOutward) {
      // Stay open for inward phase
      prefetchInward(item.value.trim());
      setOpen(true);
    } else {
      setOpen(false);
      const parts = item.value.trim().toUpperCase().split(/\s+/);
      if (parts.length === 2) {
        const geo = getGeo(parts[0], parts[1]);
        if (geo) {
          onSelect?.(item.value.trim(), geo);
          onValidate?.(true);
        }
      }
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (showSuggestions) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, suggestions.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
        return;
      }
      if (e.key === "Enter" && activeIndex >= 0) {
        e.preventDefault();
        select(suggestions[activeIndex]);
        return;
      }
      if (e.key === "Escape") {
        setOpen(false);
        return;
      }
    }
    if (e.key === "Tab") {
      setOpen(false);
      return;
    }
    if (e.key === "Enter") {
      setOpen(false);
      onKeyDown?.(e);
      return;
    }
    onKeyDown?.(e);
  }

  return (
    <div ref={containerRef} className="relative">
      <TextInput
        label={label}
        value={value}
        className={
          error || outwardInvalid || formatInvalid
            ? "!border-red-500 ring-2 ring-red-500 !outline-none"
            : ""
        }
        onChange={(e) => {
          onChange(e.currentTarget.value);
          setOpen(true);
        }}
        onFocus={() => setOpen(true)}
        onKeyDown={handleKeyDown}
        placeholder="e.g. BA1 1AA"
        maxLength={8}
        autoComplete="off"
        role="combobox"
        aria-expanded={showSuggestions}
        aria-autocomplete="list"
        aria-controls={showSuggestions ? listboxId : undefined}
        aria-activedescendant={
          activeIndex >= 0 ? `${listboxId}-option-${activeIndex}` : undefined
        }
        aria-describedby={ariaDescribedBy}
        aria-invalid={ariaInvalid}
        aria-description="Start typing a postcode to get auto-completions"
      />
      {(showSuggestions || showLoadingHint) && (
        <ul
          id={listboxId}
          role="listbox"
          tabIndex={-1}
          className="absolute z-10 mt-1 w-full bg-white border border-zinc-300 rounded-lg shadow-lg overflow-hidden max-h-60 overflow-y-auto"
        >
          {showLoadingHint && (
            <li className="px-4 py-2.5 text-base text-zinc-600">Loading...</li>
          )}
          {suggestions.map((item, i) => (
            <li
              key={item.label}
              id={`${listboxId}-option-${i}`}
              role="option"
              aria-selected={i === activeIndex}
              className={`px-4 py-2.5 text-base cursor-pointer ${
                i === activeIndex
                  ? "bg-purple-100 text-purple-900"
                  : "hover:bg-zinc-50"
              }`}
              onMouseDown={() => select(item)}
            >
              {item.label}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
