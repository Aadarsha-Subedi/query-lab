import { clsx, type ClassValue } from 'clsx'
import { extendTailwindMerge } from 'tailwind-merge'

// Our type scale (tokens.css) uses names tailwind-merge does not know; without
// this, `text-h1 text-foreground` would drop the size as a colour conflict.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      'font-size': [{ text: ['display', 'h1', 'h2', 'h3', 'body-lg', 'body', 'small', 'caption', 'code'] }],
    },
  },
})

/** Join class names; later Tailwind classes win over earlier conflicting ones. */
export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}
