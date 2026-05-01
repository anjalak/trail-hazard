"use client";

import { FormEvent, KeyboardEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { StatusMessage } from "@/components/StatusMessage";
import { searchTrailsByName } from "@/lib/graphql";
import { Trail } from "@/types";

export function SearchBar() {
  const [query, setQuery] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(
    "Start typing a trail name; suggestions appear as you type."
  );
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<Trail[]>([]);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [activeIndex, setActiveIndex] = useState<number>(-1);
  const router = useRouter();
  const hasTypedQuery = query.trim().length > 0;
  const listboxId = "trail-search-suggestions";
  const listboxVisible = isDropdownOpen && hasTypedQuery && suggestions.length > 0;
  const statusId = "trail-search-status";
  const errorId = "trail-search-error";
  const activeTrail = useMemo(() => {
    if (activeIndex < 0 || activeIndex >= suggestions.length) {
      return null;
    }
    return suggestions[activeIndex];
  }, [activeIndex, suggestions]);

  function closeDropdown() {
    setIsDropdownOpen(false);
    setActiveIndex(-1);
  }

  function openDropdown() {
    if (suggestions.length) {
      setIsDropdownOpen(true);
    }
  }

  function selectTrail(trail: Trail) {
    setQuery(trail.name);
    closeDropdown();
    router.push(`/trails/${trail.id}`);
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setStatus(null);

    if (!query.trim()) {
      setError("Enter a trail name to search.");
      return;
    }

    try {
      setLoading(true);
      const hits = await searchTrailsByName(query);
      setSuggestions(hits);
      setIsDropdownOpen(true);
      setActiveIndex(hits.length ? 0 : -1);
      if (!hits.length) {
        setStatus(`No trails match "${query}".`);
        return;
      }
      if (hits.length === 1) {
        router.push(`/trails/${hits[0].id}`);
        return;
      }
      setStatus(`Found ${hits.length} trails. Use arrows + Enter to open one.`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
      setSuggestions([]);
      closeDropdown();
    } finally {
      setLoading(false);
    }
  }

  async function onQueryChange(value: string) {
    setQuery(value);
    setError(null);
    setStatus(null);

    if (!value.trim()) {
      setSuggestions([]);
      closeDropdown();
      return;
    }

    try {
      const hits = await searchTrailsByName(value);
      setSuggestions(hits);
      setActiveIndex(hits.length ? 0 : -1);
      setIsDropdownOpen(Boolean(hits.length));
    } catch {
      setSuggestions([]);
      closeDropdown();
    }
  }

  function onInputKeyDown(event: KeyboardEvent<HTMLInputElement>) {
    if (!isDropdownOpen || !suggestions.length) {
      if (event.key === "ArrowDown" && suggestions.length) {
        event.preventDefault();
        setIsDropdownOpen(true);
        setActiveIndex(0);
      }
      return;
    }

    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => (index + 1) % suggestions.length);
      return;
    }

    if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => (index <= 0 ? suggestions.length - 1 : index - 1));
      return;
    }

    if (event.key === "Enter") {
      if (activeTrail) {
        event.preventDefault();
        selectTrail(activeTrail);
      }
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      closeDropdown();
    }
  }

  const describedBy = [error && errorId, status && statusId].filter(Boolean).join(" ") || undefined;
  const controlClassName =
    "min-h-[44px] w-full rounded-md border border-borderSubtle bg-[#f8fbfb] px-3 py-2 text-base text-appText placeholder:text-[#667271] focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 sm:text-sm";

  return (
    <form onSubmit={onSubmit} className="space-y-3" noValidate>
      <label id="trail-search-label" htmlFor="trail-search" className="block text-sm font-medium text-[#26373a]">
        Search a trail by name
      </label>
      <div className="flex flex-col gap-2 sm:flex-row sm:items-stretch">
        <div className="relative min-w-0 flex-1">
          <input
            id="trail-search"
            type="text"
            name="trailQuery"
            value={query}
            onChange={(event) => void onQueryChange(event.target.value)}
            onKeyDown={onInputKeyDown}
            onFocus={openDropdown}
            onBlur={() => {
              window.setTimeout(() => closeDropdown(), 120);
            }}
            role="combobox"
            aria-haspopup="listbox"
            aria-autocomplete="list"
            aria-expanded={listboxVisible}
            aria-controls={listboxVisible ? listboxId : undefined}
            aria-activedescendant={listboxVisible && activeTrail ? `trail-option-${activeTrail.id}` : undefined}
            aria-labelledby="trail-search-label"
            aria-busy={loading}
            aria-invalid={Boolean(error)}
            aria-describedby={describedBy}
            autoComplete="off"
            className={controlClassName}
            placeholder="Snow Lake Trail"
          />
          {listboxVisible ? (
            <ul
              id={listboxId}
              role="listbox"
              aria-label="Matching trails"
              className="absolute left-0 right-0 top-full z-10 mt-1 max-h-64 overflow-y-auto rounded-md border border-borderSubtle bg-surface p-1 shadow-floating"
            >
              {suggestions.map((trail, index) => {
                const isActive = index === activeIndex;
                return (
                  <li
                    key={trail.id}
                    id={`trail-option-${trail.id}`}
                    role="option"
                    aria-selected={isActive}
                    className={`cursor-pointer rounded px-3 py-3 text-sm sm:py-2 ${
                      isActive ? "bg-[#202f32] text-white" : "text-[#2f3d3f] hover:bg-surfaceMuted"
                    }`}
                    onMouseDown={(event) => {
                      event.preventDefault();
                      selectTrail(trail);
                    }}
                  >
                    <p className="font-medium">{trail.name}</p>
                    <p className={`text-xs ${isActive ? "text-[#f0f5d4]" : "text-[#5c6766]"}`}>
                      {trail.region}
                      {trail.location?.city ? ` - ${trail.location.city}` : ""}
                      {trail.location?.state_code ? `, ${trail.location.state_code}` : ""}
                    </p>
                  </li>
                );
              })}
            </ul>
          ) : null}
        </div>
        <button
          type="submit"
          disabled={loading}
          aria-busy={loading}
          className="min-h-[44px] w-full shrink-0 rounded-md border border-accent bg-[#1f3033] px-4 py-2 text-sm font-semibold text-white shadow-sm hover:border-accentSoft hover:bg-[#17282a] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 disabled:opacity-60 sm:w-auto"
        >
          {loading ? "Searching..." : "Search"}
        </button>
      </div>
      {error ? (
        <StatusMessage id={errorId} role="alert" tone="error" message={error} />
      ) : null}
      {status ? (
        <StatusMessage id={statusId} role="status" ariaLive="polite" message={status} />
      ) : null}
    </form>
  );
}
