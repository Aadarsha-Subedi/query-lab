import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

/** localStorage key for the SQL typed in the Query sheet, per workspace. */
export const QUERY_DRAFT_KEY = 'querylab-query-drafts'

type QueryDraftState = {
  /** The last SQL entered, by workspace id. UI-only state, kept across closing the sheet and reloads. */
  drafts: Record<number, string>
  setDraft: (workspaceId: number, sql: string) => void
}

export const useQueryDraftStore = create<QueryDraftState>()(
  persist(
    (set) => ({
      drafts: {},
      setDraft: (workspaceId, sql) => {
        set((state) => ({ drafts: { ...state.drafts, [workspaceId]: sql } }))
      },
    }),
    { name: QUERY_DRAFT_KEY, storage: createJSONStorage(() => localStorage) },
  ),
)
