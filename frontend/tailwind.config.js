import colors from 'tailwindcss/colors'
import frappeUIPreset from 'frappe-ui/tailwind'
import { ALL_ICON_NAMES } from './src/utils/layout/sidebarIcons.js'
import { DASHBOARD_ICON_NAMES } from './src/utils/dashboard/icons.js'

export default {
  presets: [frappeUIPreset],
  content: [
    './index.html',
    './src/**/*.{vue,js,ts,jsx,tsx}',
    './node_modules/frappe-ui/src/components/**/*.{vue,js,ts,jsx,tsx}',
  ],
  // AppSidebar/CommandPalette build icon classes as `'lucide-' + name` at
  // runtime (the name comes from sidebar config data), so Tailwind's static
  // content scan can't discover them - safelist the closed vocabulary from
  // sidebarIcons.js instead. The dashboard's cards do the same with names
  // that come from the server and from utils/dashboard/icons.js.
  safelist: [...ALL_ICON_NAMES, ...DASHBOARD_ICON_NAMES].map((name) => `lucide-${name}`),
  theme: {
    extend: {
      colors: {
        // frappe-ui's preset replaces Tailwind's palette and ships only
        // amber/blue/green/red/violet (+ its own grays), so classes like
        // bg-emerald-500 or border-sky-300 silently generated nothing - no
        // dots on the Chart of Accounts, no info banners. Bring back the
        // families this app uses.
        emerald: colors.emerald,
        rose: colors.rose,
        sky: colors.sky,
        teal: colors.teal,
        pink: colors.pink,
        indigo: colors.indigo,
        slate: colors.slate,
        // brand blue, derived from the Vrugle "/V" logo mark (#0057E5)
        brand: {
          50: '#F0F6FF',
          100: '#DBE9FF',
          200: '#B2D0FF',
          300: '#7AADFF',
          400: '#3381FF',
          500: '#0057E5',
          600: '#0051D6',
          700: '#0042AD',
          800: '#00348A',
          900: '#002766',
          950: '#001942',
        },
        // theme-aware app surface/text tokens (see src/index.css for the
        // light/dark values behind these variables)
        app: {
          bg: 'var(--app-bg)',
          panel: 'var(--app-panel)',
          'panel-2': 'var(--app-panel-2)',
          border: 'var(--app-border)',
          text: 'var(--app-text)',
          'text-muted': 'var(--app-text-muted)',
          primary: 'var(--app-primary)',
          'primary-hover': 'var(--app-primary-hover)',
          'primary-tint': 'var(--app-primary-tint)',
        },
      },
    },
  },
}
