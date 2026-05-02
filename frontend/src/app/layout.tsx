import "./globals.css";
import { type CSSProperties, type ReactNode } from "react";

import { SiteFooter } from "@/components/SiteFooter";
import { SkipLink } from "@/components/SkipLink";
import contourBackground from "../../topography-contour-map-design/12315.jpg";

export const metadata = {
  title: "TrailIntel",
  description: "Trail conditions and hazard intelligence"
};

const topoBackdropStyle: CSSProperties = {
  backgroundColor: "#5d4f43",
  backgroundImage: `linear-gradient(rgba(25, 55, 44, 0.52), rgba(25, 55, 44, 0.52)), linear-gradient(rgba(93, 79, 67, 0.28), rgba(93, 79, 67, 0.28)), url(${contourBackground.src})`,
  backgroundBlendMode: "multiply, normal, normal",
  backgroundSize: "cover",
  backgroundPosition: "center",
  backgroundRepeat: "no-repeat"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body className="relative font-body text-appText">
        {/* Fixed full-viewport layer (not background-attachment:fixed) — smoother scrolling on long pages */}
        <div aria-hidden className="pointer-events-none fixed inset-0 -z-10" style={topoBackdropStyle} />
        <SkipLink />
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto flex min-h-screen max-w-5xl flex-col px-4 py-5 outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 focus-visible:ring-offset-appBg sm:px-6 sm:py-8"
        >
          <div className="flex-1">{children}</div>
          <SiteFooter />
        </main>
      </body>
    </html>
  );
}
