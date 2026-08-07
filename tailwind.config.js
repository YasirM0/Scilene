/** @type {import('tailwindcss').Config} */
module.exports = {
  // Scans the actual Jinja2 templates for classes in use, so the built
  // CSS only contains what's really referenced -- this is what makes
  // the CLI build "production" rather than the Tailwind CDN script
  // (which ships the entire framework, unminified, and is explicitly
  // called out in Tailwind's own docs as not for production use).
  content: ["./web/templates/**/*.html"],
  theme: {
    extend: {
      // Brand identity (docs/DESIGN_SYSTEM.md). Each color's 500/600/700
      // shades are derived from its base hex by a fixed lighten/darken
      // percentage, not hand-picked -- see DESIGN_SYSTEM.md for the formula.
      colors: {
        navy: {
          DEFAULT: "#1E3A5F",
          600: "#1E3A5F",
          700: "#182E4C",
        },
        horizon: {
          50: "#F0F4F7",
          500: "#6386A6",
          DEFAULT: "#2F5E88",
          600: "#2F5E88",
          700: "#264B6D",
        },
        gold: {
          DEFAULT: "#C9A227",
          600: "#C9A227",
          700: "#A1821F",
        },
      },
    },
  },
  plugins: [],
};
