/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // ACH-specific colors
        'ach-cc': '#22c55e',  // Very Consistent - green
        'ach-c': '#84cc16',   // Consistent - lime
        'ach-n': '#6b7280',   // Neutral - gray
        'ach-i': '#f97316',   // Inconsistent - orange
        'ach-ii': '#ef4444',  // Very Inconsistent - red
      },
    },
  },
  plugins: [],
}
