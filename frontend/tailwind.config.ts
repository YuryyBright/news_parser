// tailwind.config.ts
import type { Config } from "tailwindcss";
import typography from "@tailwindcss/typography";
import forms from "@tailwindcss/forms";

export default {
  // Вказуємо шлях до всіх файлів, де використовуються класи Tailwind
  content: ["./index.html", "./src/**/*.{ts,tsx}"],

  // Активація темного режиму через клас (зазвичай на тегу html або body)
  darkMode: "class",

  theme: {
    extend: {
      fontFamily: {
        // Твої кастомні шрифти з конфігу
        sans: ["Plus Jakarta Sans", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "monospace"],
      },
      animation: {
        "fade-in": "fadeIn 0.2s ease-out",
        "slide-in": "slideIn 0.3s ease-out",
      },
      keyframes: {
        fadeIn: {
          from: { opacity: "0", transform: "translateY(4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        slideIn: {
          from: { transform: "translateX(100%)" },
          to: { transform: "translateX(0)" },
        },
      },
    },
  },

  // Підключення плагінів, які є у твоєму package.json
  plugins: [typography, forms],
} satisfies Config;
