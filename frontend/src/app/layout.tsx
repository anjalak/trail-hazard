import "./globals.css";
import { ReactNode } from "react";

import { SkipLink } from "@/components/SkipLink";
import contourBackground from "../../topography-contour-map-design/12315.jpg";

export const metadata = {
  title: "TrailIntel",
  description: "Trail conditions and hazard intelligence"
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body
        className="font-body text-appText"
        style={{
          backgroundColor: "#5d4f43",
          backgroundImage: `linear-gradient(rgba(25, 55, 44, 0.52), rgba(25, 55, 44, 0.52)), linear-gradient(rgba(93, 79, 67, 0.28), rgba(93, 79, 67, 0.28)), url(${contourBackground.src})`,
          backgroundBlendMode: "multiply, normal, normal",
          backgroundSize: "cover",
          backgroundPosition: "center",
          backgroundRepeat: "no-repeat",
          backgroundAttachment: "fixed"
        }}
      >
        <SkipLink />
        <main
          id="main-content"
          tabIndex={-1}
          className="mx-auto min-h-screen max-w-5xl px-4 py-5 outline-none focus-visible:ring-2 focus-visible:ring-focusRing focus-visible:ring-offset-2 focus-visible:ring-offset-appBg sm:px-6 sm:py-8"
        >
          {children}
        </main>
      </body>
    </html>
  );
}
