/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          DEFAULT: "#dc2626",
          50: "#1a0a0a",
          100: "#2d1111",
          200: "#491b1b",
          300: "#7f1d1d",
          400: "#b91c1c",
          500: "#dc2626",
          600: "#ef4444",
          700: "#f87171",
        },
        accent: { DEFAULT: "#dc2626", 500: "#dc2626" },
        dark: {
          bg: "#0a0a0a",
          card: "#111111",
          border: "#1e1e1e",
          hover: "#1a1a1a",
          text: "#e5e5e5",
          muted: "#737373",
          surface: "#161616",
        },
      },
    },
  },
  plugins: [require("@tailwindcss/typography")],
};
