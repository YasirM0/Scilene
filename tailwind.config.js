/** @type {import('tailwindcss').Config} */
module.exports = {
  // Scans the actual Jinja2 templates for classes in use, so the built
  // CSS only contains what's really referenced -- this is what makes
  // the CLI build "production" rather than the Tailwind CDN script
  // (which ships the entire framework, unminified, and is explicitly
  // called out in Tailwind's own docs as not for production use).
  content: ["./web/templates/**/*.html"],
  // "class" (not the default "media") because dark mode is the
  // default appearance (v0.2.5 Issue 4) with an explicit opt-out to
  // light, not just a mirror of the OS setting -- toggled by adding/
  // removing "dark" on <html>, see base.html's inline init script.
  darkMode: "class",
  theme: {
    extend: {
      // Brand identity (docs/DESIGN_SYSTEM.md). Each color's 500/600/700
      // shades are derived from its base hex by a fixed lighten/darken
      // percentage, not hand-picked -- see DESIGN_SYSTEM.md for the formula.
      colors: {
        navy: {
          50: "#EFF1F4",
          // 300 is NOT a mechanically-derived tint like the others --
          // it's picked for AA contrast on a dark (gray-800/900)
          // background specifically, since navy-600 (correct on white)
          // reads as near-invisible dark-on-dark. Dark-mode heading/
          // link text uses this instead of navy-600; solid-fill navy
          // buttons (white text on top) are unaffected and stay 600
          // in both themes.
          300: "#8CA3BE",
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
          50: "#FBF8F0",
          DEFAULT: "#C9A227",
          600: "#C9A227",
          700: "#A1821F",
        },
      },
    },
  },
  plugins: [],
};
