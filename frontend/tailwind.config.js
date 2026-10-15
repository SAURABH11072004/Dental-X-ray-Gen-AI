/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        navy: { DEFAULT: "#15304B", 700: "#1d3f60", 100: "#e3eaf1" },
        teal: { DEFAULT: "#0D7D7F", 700: "#0c6f71", 50: "#e6f4f4" },
        canvas: "#F5F7FA",
        ink: "#1C2938",
        muted: "#55657A",
        line: "#E2E8F0",
        ok: "#158067",
        warn: "#A75B04",
        bad: "#C44343",
      },
      fontFamily: { sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "Roboto", "sans-serif"] },
      boxShadow: { card: "0 1px 2px rgba(21,48,75,0.06), 0 1px 3px rgba(21,48,75,0.04)" },
    },
  },
  plugins: [],
};
