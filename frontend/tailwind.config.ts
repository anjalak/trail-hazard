import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}"
  ],
  theme: {
    extend: {
      colors: {
        appBg: "#5d4f43",
        appText: "#142224",
        surface: "#9eb6b0",
        surfaceMuted: "#8da6a0",
        borderSubtle: "#6f8b84",
        focusRing: "#b6ea42",
        brand: "#2b3d40",
        brandContrast: "#ffffff",
        accent: "#c6ee41",
        accentSoft: "#e0f48a",
        signal: "#d9423a"
      },
      fontFamily: {
        display: ["Helvetica Neue", "Helvetica", "Arial", "sans-serif"],
        body: ["Inter", "Arial", "sans-serif"]
      },
      boxShadow: {
        card: "0 1px 2px rgba(29, 42, 34, 0.08), 0 10px 24px rgba(29, 42, 34, 0.04)",
        floating: "0 14px 30px rgba(29, 42, 34, 0.12)"
      },
      borderRadius: {
        panel: "1rem"
      },
      maxWidth: {
        app: "72rem"
      },
      spacing: {
        pageX: "1rem",
        pageY: "1.5rem",
        section: "1.5rem"
      }
    }
  },
  plugins: []
};

export default config;
