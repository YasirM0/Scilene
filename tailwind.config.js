/** @type {import('tailwindcss').Config} */
module.exports = {
  // Scans the actual Jinja2 templates for classes in use, so the built
  // CSS only contains what's really referenced -- this is what makes
  // the CLI build "production" rather than the Tailwind CDN script
  // (which ships the entire framework, unminified, and is explicitly
  // called out in Tailwind's own docs as not for production use).
  content: ["./web/templates/**/*.html"],
  theme: {
    extend: {},
  },
  plugins: [],
};
