"use client";

import { useCallback, useState } from "react";

type CopyCodeBlockProps = {
  code: string;
  copyLabel?: string;
};

export function CopyCodeBlock({ code, copyLabel = "Copy snippet" }: CopyCodeBlockProps) {
  const [copied, setCopied] = useState(false);

  const onCopy = useCallback(async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopied(false);
    }
  }, [code]);

  return (
    <div className="overflow-hidden rounded-lg border border-borderSubtle bg-[#142224]">
      <div className="flex items-center justify-end gap-2 border-b border-white/10 px-3 py-2">
        <button
          type="button"
          onClick={onCopy}
          className="rounded px-2.5 py-1 text-xs font-medium text-[#c9ddd9] underline-offset-2 hover:bg-white/5 hover:text-[#f4ede3] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 focus-visible:ring-offset-[#142224]"
        >
          {copied ? "Copied" : copyLabel}
        </button>
      </div>
      <pre className="overflow-x-auto p-4 text-xs leading-relaxed text-[#f4ede3]">
        <code>{code}</code>
      </pre>
    </div>
  );
}
