/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        page: "#0d0d0d",
        surface: "#1a1a19",
        raised: "#232322",
        ink: "#ffffff",
        sub: "#c3c2b7",
        muted: "#898781",
        hairline: "rgba(255,255,255,0.10)",
        grid: "#2c2c2a",
        // categorical slots (dark mode, validated all-pairs for 3 series)
        s1: "#3987e5",
        s2: "#d95926",
        s3: "#199e70",
        good: "#0ca30c",
        warning: "#fab219",
        serious: "#ec835a",
        critical: "#d03b3b",
      },
      fontFamily: {
        sans: ["IBM Plex Sans", "system-ui", "sans-serif"],
        mono: ["IBM Plex Mono", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
