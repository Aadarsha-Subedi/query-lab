import { create } from 'zustand'

/** Which tables are expanded in the schema panel. UI only; the schema itself is in Query. */
type SchemaPanelState = {
  open: Record<string, boolean>
  toggle: (table: string) => void
}

export const useSchemaPanelStore = create<SchemaPanelState>()((set) => ({
  open: {},
  toggle: (table) => {
    set((state) => ({ open: { ...state.open, [table]: !state.open[table] } }))
  },
}))
