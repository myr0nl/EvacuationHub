/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./src/**/*.{js,jsx,ts,tsx}",
    "./public/index.html"
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Helvetica Neue', 'Arial', 'sans-serif'],
      },
      colors: {
        // Enhanced disaster severity colors - 2025 Modern Palette
        critical: {
          DEFAULT: '#ef4444',  // Red 500 - Softer but still urgent
          light: '#fca5a5',     // Red 300 - For glows/highlights
          dark: '#b91c1c',      // Red 700 - For dark mode
          glow: 'rgba(239, 68, 68, 0.5)'
        },
        warning: {
          DEFAULT: '#f97316',  // Orange 500 - More vibrant visibility
          light: '#fdba74',     // Orange 300 - For glows/highlights
          dark: '#c2410c',      // Orange 700 - For dark mode
          glow: 'rgba(249, 115, 22, 0.5)'
        },
        caution: {
          DEFAULT: '#fbbf24',  // Amber 400 - Warmer, more noticeable
          light: '#fcd34d',     // Amber 300 - For glows/highlights
          dark: '#d97706',      // Amber 600 - For dark mode
          glow: 'rgba(251, 191, 36, 0.5)'
        },
        success: {
          DEFAULT: '#22c55e',  // Green 500 - More vibrant "safe" signal
          light: '#86efac',     // Green 300 - For glows/highlights
          dark: '#15803d',      // Green 700 - For dark mode
          glow: 'rgba(34, 197, 94, 0.5)'
        },
        info: {
          DEFAULT: '#14b8a6',  // Teal 500 - Calming ocean/nature vibe
          light: '#5eead4',     // Teal 300 - For glows/highlights
          dark: '#0f766e',      // Teal 700 - For dark mode
          glow: 'rgba(20, 184, 166, 0.5)'
        },
        // Nature-inspired brand colors - Sage to Emerald gradient (calming & professional)
        primary: {
          DEFAULT: '#7a9d7a',  // Sage Green - Calming, natural wisdom
          light: '#a8c5a8',     // Light Sage - For glows/highlights
          dark: '#5a7d5a',      // Dark Sage - For dark mode
          glow: 'rgba(122, 157, 122, 0.5)'
        },
        secondary: {
          DEFAULT: '#34a864',  // Emerald Green - Professional, confident
          light: '#6bc992',     // Light Emerald - For glows/highlights
          dark: '#2a8650',      // Dark Emerald - For dark mode
          glow: 'rgba(52, 168, 100, 0.5)'
        },
        // Neutral colors
        neutral: {
          50: '#f9fafb',
          100: '#f3f4f6',
          200: '#e5e7eb',
          300: '#d1d5db',
          400: '#9ca3af',
          500: '#6b7280',
          600: '#4b5563',
          700: '#374151',
          800: '#1f2937',
          900: '#111827',
          950: '#030712'
        }
      },
      backgroundImage: {
        'gradient-primary': 'linear-gradient(135deg, #7a9d7a 0%, #34a864 100%)',  // Sage to Emerald - Calming nature gradient
        'gradient-critical': 'linear-gradient(135deg, #ef4444 0%, #b91c1c 100%)',  // Red 500 to Red 700
        'gradient-warning': 'linear-gradient(135deg, #f97316 0%, #c2410c 100%)',   // Orange 500 to Orange 700
        'gradient-success': 'linear-gradient(135deg, #22c55e 0%, #15803d 100%)',   // Green 500 to Green 700
        'gradient-info': 'linear-gradient(135deg, #14b8a6 0%, #0f766e 100%)',      // Teal 500 to Teal 700 - Calming ocean
      },
      boxShadow: {
        'glass': '0 8px 32px rgba(0, 0, 0, 0.1)',
        'glass-lg': '0 12px 48px rgba(0, 0, 0, 0.15)',
        'glow-critical': '0 0 20px rgba(239, 68, 68, 0.5)',     // Red glow
        'glow-warning': '0 0 20px rgba(249, 115, 22, 0.5)',     // Orange glow
        'glow-success': '0 0 20px rgba(34, 197, 94, 0.5)',      // Green glow
        'glow-info': '0 0 20px rgba(20, 184, 166, 0.5)',        // Teal glow - Calming
        'glow-primary': '0 0 20px rgba(122, 157, 122, 0.5)',    // Sage green glow - Nature
      },
      backdropBlur: {
        xs: '2px',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-in-out',
        'fade-out': 'fadeOut 0.3s ease-in-out',
        'slide-in-right': 'slideInRight 0.3s ease-out',
        'slide-in-left': 'slideInLeft 0.3s ease-out',
        'slide-in-up': 'slideInUp 0.3s ease-out',
        'slide-in-down': 'slideInDown 0.3s ease-out',
        'pulse-slow': 'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'spin-slow': 'spin 3s linear infinite',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' }
        },
        fadeOut: {
          '0%': { opacity: '1' },
          '100%': { opacity: '0' }
        },
        slideInRight: {
          '0%': { transform: 'translateX(100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' }
        },
        slideInLeft: {
          '0%': { transform: 'translateX(-100%)', opacity: '0' },
          '100%': { transform: 'translateX(0)', opacity: '1' }
        },
        slideInUp: {
          '0%': { transform: 'translateY(100%)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' }
        },
        slideInDown: {
          '0%': { transform: 'translateY(-20px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' }
        },
        pulseGlow: {
          '0%, 100%': { boxShadow: '0 0 20px rgba(122, 157, 122, 0.3)' },  // Sage green glow
          '50%': { boxShadow: '0 0 40px rgba(122, 157, 122, 0.6)' }
        }
      },
      transitionDuration: {
        '400': '400ms',
      },
    },
  },
  plugins: [],
}
