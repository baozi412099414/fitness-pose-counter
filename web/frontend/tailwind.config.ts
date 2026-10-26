import type { Config } from "tailwindcss";

/**
 * 颜色 token 全部走 RGB 通道变量（定义在 globals.css 的 :root），
 * 这样 bg-accent/10 之类的透明度写法能正常工作。
 */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        "bg0": "rgb(var(--bg-0-rgb) / <alpha-value>)",
        "bg1": "rgb(var(--bg-1-rgb) / <alpha-value>)",
        "surface1": "rgb(var(--surface-1-rgb) / <alpha-value>)",
        "surface2": "rgb(var(--surface-2-rgb) / <alpha-value>)",
        "surface3": "rgb(var(--surface-3-rgb) / <alpha-value>)",
        "line1": "rgb(var(--line-1-rgb) / <alpha-value>)",
        "line2": "rgb(var(--line-2-rgb) / <alpha-value>)",
        "text1": "rgb(var(--text-1-rgb) / <alpha-value>)",
        "text2": "rgb(var(--text-2-rgb) / <alpha-value>)",
        "text3": "rgb(var(--text-3-rgb) / <alpha-value>)",
        "accent": "rgb(var(--accent-rgb) / <alpha-value>)",
        "accentInk": "rgb(var(--accent-ink-rgb) / <alpha-value>)",
        "cyan": "rgb(var(--cyan-rgb) / <alpha-value>)",
        "amber": "rgb(var(--amber-rgb) / <alpha-value>)",
        "coral": "rgb(var(--coral-rgb) / <alpha-value>)",
        "mint": "rgb(var(--mint-rgb) / <alpha-value>)",
      },
      fontFamily: {
        display: [
          '"Bebas Neue"',
          '"DIN Condensed"',
          "Impact",
          "sans-serif",
        ],
        ui: [
          '"MiSans"',
          '"HarmonyOS Sans SC"',
          '"PingFang SC"',
          '"Microsoft YaHei"',
          "system-ui",
          "sans-serif",
        ],
        mono: [
          '"Space Grotesk"',
          '"JetBrains Mono"',
          '"SFMono-Regular"',
          "Consolas",
          "monospace",
        ],
      },
      borderRadius: {
        card: "14px",
        stage: "20px",
        dialog: "18px",
      },
      transitionTimingFunction: {
        form: "cubic-bezier(.2,.8,.2,1)",
      },
      keyframes: {
        "breathe": {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(8px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        skeleton: "breathe 1.2s cubic-bezier(.2,.8,.2,1) infinite",
        "fade-in-up": "fade-in-up 160ms cubic-bezier(.2,.8,.2,1) both",
      },
    },
  },
  plugins: [],
} satisfies Config;