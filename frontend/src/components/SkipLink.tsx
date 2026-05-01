export function SkipLink() {
  return (
    <a
      href="#main-content"
      className="fixed left-4 top-4 z-[100] translate-y-[-130%] opacity-0 rounded-md bg-white px-4 py-3 text-sm font-medium text-slate-900 shadow-lg ring-2 ring-slate-900 ring-offset-2 ring-offset-slate-50 transition-all duration-150 ease-out focus-visible:translate-y-0 focus-visible:opacity-100 focus-visible:outline-none"
    >
      Skip to main content
    </a>
  );
}
