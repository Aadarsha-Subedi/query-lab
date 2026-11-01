import { create } from 'zustand'

/** UI-only state shared across screens. Server data never goes here. */
type UiState = {
  /** The side navigation as a sheet on narrow screens. */
  navOpen: boolean
  setNavOpen: (open: boolean) => void
}

export const useUiStore = create<UiState>()((set) => ({
  navOpen: false,
  setNavOpen: (navOpen) => {
    set({ navOpen })
  },
}))
