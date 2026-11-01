import { useQueryClient } from '@tanstack/react-query'

/** Everything that depends on the saved keys or the chosen source. */
export function useRefresh() {
  const queryClient = useQueryClient()
  return async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['llm-keys'] }),
      queryClient.invalidateQueries({ queryKey: ['llm-settings'] }),
      queryClient.invalidateQueries({ queryKey: ['agent-limits'] }),
    ])
  }
}
