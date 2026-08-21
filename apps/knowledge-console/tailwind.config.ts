import type { Config } from "tailwindcss";

// Bloomberg-terminal design system. term.* tokens are the single palette source;
// components reference only these, never raw hex.
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        term: {
          bg: "#0A0A0A",
          panel: "#111113",
          "panel-2": "#161619",
          border: "#26262B",
          "border-2": "#33333A",
          amber: "#FF8C00",
          "amber-dim": "#B36400",
          up: "#2ECC71",
          down: "#FF3B3B",
          text: "#E6E6E6",
          dim: "#9A9AA3",
          muted: "#5E5E66",
          info: "#4F9CF9",
        },
      },
      fontFamily: {
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "SF Mono",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
        sans: ["system-ui", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
      },
      fontSize: {
        "3xs": ["9px", { lineHeight: "12px" }],
        "2xs": ["10px", { lineHeight: "14px" }],
      },
      keyframes: {
        flashUp: {
          "0%": { backgroundColor: "rgba(46,204,113,0.35)" },
          "100%": { backgroundColor: "transparent" },
        },
        flashDown: {
          "0%": { backgroundColor: "rgba(255,59,59,0.35)" },
          "100%": { backgroundColor: "transparent" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        scan: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100%)" },
        },
      },
      animation: {
        flashUp: "flashUp 0.6s ease-out",
        flashDown: "flashDown 0.6s ease-out",
        blink: "blink 1.2s step-start infinite",
        scan: "scan 6s linear infinite",
      },
    },
  },
  plugins: [],
} satisfies Config;
