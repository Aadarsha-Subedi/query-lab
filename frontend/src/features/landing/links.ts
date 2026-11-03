/** Where the landing and legal pages point. */
export const REPO_URL = 'https://github.com/Aadarsha-Subedi/query-lab'
export const ISSUES_URL = `${REPO_URL}/issues`
export const OLIST_LICENCE_URL = 'https://creativecommons.org/licenses/by-nc-sa/4.0/'

/** Change this whenever the Privacy Policy or the Terms change. */
export const LEGAL_LAST_UPDATED = '2026-11-03'

/** Section ids on the landing page: the navbar links to them. */
export const LANDING_SECTIONS = [
  { hash: 'how-it-works', label: 'How it works' },
  { hash: 'features', label: 'Features' },
  { hash: 'evals', label: 'Evals' },
  { hash: 'faq', label: 'FAQ' },
] as const
