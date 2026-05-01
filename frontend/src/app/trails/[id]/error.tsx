"use client";

import Link from "next/link";

type Props = {
  error: Error;
  reset: () => void;
};

export default function TrailDetailsError({ error, reset }: Props) {
  return (
    <div className="space-y-4 rounded-xl border border-red-200 bg-red-50 p-4 sm:p-6">
      <h1 className="text-lg font-semibold text-red-800 sm:text-xl">Could not load trail details</h1>
      <p className="text-sm text-red-700" role="alert">
        {error.message || "Try again in a moment."}
      </p>
      <div className="flex flex-col gap-2 sm:flex-row sm:gap-3">
        <button
          type="button"
          onClick={reset}
          className="min-h-[44px] rounded-md border border-accent bg-[#1f3033] px-4 py-2.5 text-sm font-semibold text-white shadow-sm hover:border-accentSoft hover:bg-[#17282a] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 sm:min-h-0 sm:py-2"
        >
          Try again
        </button>
        <Link
          href="/"
          className="inline-flex min-h-[44px] items-center justify-center rounded-md border border-borderSubtle bg-surface px-4 py-2.5 text-center text-sm font-medium text-appText focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 sm:min-h-0 sm:py-2"
        >
          Back to search
        </Link>
      </div>
    </div>
  );
}
