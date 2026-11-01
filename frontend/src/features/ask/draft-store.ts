import { create } from 'zustand'

/** SQL the user is editing in an approval card, per run, so leaving the page does not lose it. UI only. */
type DraftState = {
  drafts: Record<number, string>
  setDraft: (runId: number, sql: string) => void
  clearDraft: (runId: number) => void
}

export const useDraftStore = create<DraftState>()((set) => ({
  drafts: {},
  setDraft: (runId, sql) => {
    set((state) => ({ drafts: { ...state.drafts, [runId]: sql } }))
  },
  clearDraft: (runId) => {
    set((state) => ({
      drafts: Object.fromEntries(Object.entries(state.drafts).filter(([id]) => Number(id) !== runId)),
    }))
  },
}))
