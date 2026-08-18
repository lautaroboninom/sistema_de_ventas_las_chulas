export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          ink: "#0b0b0d",
          paper: "#fcfbf7",
          muted: "#6a6e76",
          accent: "#ef6f61",
          "accent-dark": "#d9584b",
          "accent-soft": "#ffe8dd",
        },
      },
      fontFamily: {
        sans: ["Barlow", "Segoe UI", "sans-serif"],
        display: ["Sora", "Segoe UI", "sans-serif"],
      },
      boxShadow: {
        soft: "0 10px 30px rgba(9, 10, 12, 0.06)",
        lift: "0 18px 45px rgba(9, 10, 12, 0.12)",
      },
      keyframes: {
        "lc-pop": {
          "0%": { backgroundColor: "rgba(239, 111, 97, 0.16)" },
          "100%": { backgroundColor: "rgba(239, 111, 97, 0)" },
        },
        "lc-toast-in": {
          "0%": { opacity: "0", transform: "translateY(-6px)" },
          "100%": { opacity: "1", transform: "none" },
        },
      },
      animation: {
        "lc-pop": "lc-pop 700ms ease-out 1",
        "lc-toast-in": "lc-toast-in 180ms ease-out 1",
      },
    },
  },
  plugins: [],
};
