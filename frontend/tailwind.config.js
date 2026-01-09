/** @type {import('tailwindcss').Config} */
export default {
  content: ["./app/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        mono: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'Monaco', 'Consolas', "Liberation Mono", "Courier New", 'monospace'],
        serif: ['"Noto Serif"', 'Georgia', 'Cambria', '"Times New Roman"', 'Times', 'serif'],
      },
      // Typography scale - replaces arbitrary text-[Xpx] values
      fontSize: {
        'micro': ['0.625rem', { lineHeight: '0.875rem' }],  // 10px - badges, timestamps
        'tiny': ['0.6875rem', { lineHeight: '1rem' }],      // 11px - secondary labels
        'caption': ['0.75rem', { lineHeight: '1rem' }],     // 12px - table headers, captions
        'body': ['0.875rem', { lineHeight: '1.25rem' }],    // 14px - body text (same as text-sm)
        'title': ['1rem', { lineHeight: '1.5rem' }],        // 16px - section titles
        'heading': ['1.25rem', { lineHeight: '1.75rem' }],  // 20px - page headings
        'display': ['1.5rem', { lineHeight: '2rem' }],      // 24px - hero text
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        // Brand mint green color palette
        brand: {
          50: '#edfcf5',
          100: '#d4f7e6',
          200: '#adedd2',
          300: '#7dd3a8', // Base brand color
          400: '#4ab888',
          500: '#279d6e',
          600: '#1a7f59',
          700: '#166549',
          800: '#14503b',
          900: '#124232',
          950: '#09251c',
        },
        // Semantic colors for price changes
        success: {
          DEFAULT: "hsl(var(--success))",
          foreground: "hsl(var(--success-foreground))",
        },
        warning: {
          DEFAULT: "hsl(var(--warning))",
          foreground: "hsl(var(--warning-foreground))",
        },
      },
      // Animation for reduced motion support
      animation: {
        'spin-slow': 'spin 2s linear infinite',
      },
    },
  },
  plugins: [],
  darkMode: "class"
}

