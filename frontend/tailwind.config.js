/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: [
          "Inter",
          "ui-sans-serif",
          "system-ui",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "Menlo",
          "monospace",
        ],
      },
      colors: {
        coral: {
          DEFAULT: "#EF6344",
          hover: "#E04E2E",
          light: "rgba(239, 99, 68, 0.10)",
          subtle: "rgba(239, 99, 68, 0.06)",
        },
        sidebar: {
          DEFAULT: "rgba(24, 26, 42, 0.85)",
          hover: "rgba(255, 255, 255, 0.06)",
          active: "rgba(255, 255, 255, 0.10)",
        },
        app: "#EDEEF2",
        surface: "rgba(255, 255, 255, 0.55)",
        muted: "rgba(0, 0, 0, 0.03)",
      },
      borderRadius: {
        xl: "16px",
        "2xl": "20px",
        "3xl": "24px",
      },
      backdropBlur: {
        glass: "20px",
        "glass-heavy": "30px",
      },
    },
  },
  plugins: [],
};
