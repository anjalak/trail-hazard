import Link from "next/link";

const footerLinkClass =
  "text-sm font-medium text-appText underline decoration-accent/80 underline-offset-4 transition-colors hover:text-accent";

export function SiteFooter() {
  return (
    <footer className="mt-10">
      <nav
        aria-label="Footer"
        className="rounded-panel border border-borderSubtle bg-surface px-4 py-4 shadow-card sm:flex sm:flex-wrap sm:items-baseline sm:justify-between sm:gap-x-6 sm:px-5 sm:py-4"
      >
        <ul className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:gap-x-6 sm:gap-y-2">
          <li>
            <Link className={footerLinkClass} href="/about">
              About
            </Link>
          </li>
          <li>
            <Link className={footerLinkClass} href="/sources">
              Data sources
            </Link>
          </li>
          <li>
            <Link className={footerLinkClass} href="/api">
              API
            </Link>
          </li>
        </ul>
        <p className="mt-3 text-xs font-medium text-[#2f3d3f] sm:mt-0">TrailIntel</p>
      </nav>
    </footer>
  );
}
