import { useNavigate, useSearch } from '@tanstack/react-router'

import { WorkspaceSelect } from './WorkspaceSelect'

/**
 * The workspace picker in the top bar. It only applies to the Ask page (the workspace is that page's
 * `?workspace=` search value), so it shows there and nowhere else. Changing it leaves the open
 * question and table behind: they belonged to the other workspace.
 */
export function HeaderWorkspaceSelect() {
  const search = useSearch({ from: '/_app/ask', shouldThrow: false })
  const navigate = useNavigate()
  if (!search) return null
  return (
    <WorkspaceSelect
      className="w-36 sm:w-56"
      workspace={search.workspace}
      onChange={(workspace) => {
        void navigate({ to: '/ask', search: { tab: search.tab, workspace } })
      }}
    />
  )
}
