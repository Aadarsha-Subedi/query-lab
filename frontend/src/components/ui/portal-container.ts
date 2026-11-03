import { createContext } from 'react'

/**
 * Where popups (a Select's list) should render. A modal dialog (Radix) traps focus and treats anything
 * outside itself as an outside click, which closes a popup portalled to the page body the moment it
 * opens. The dialog provides its own element here so the popup lives inside it.
 */
export const PortalContainerContext = createContext<HTMLElement | null>(null)
