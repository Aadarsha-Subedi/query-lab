/** Adds the optional `?workspace=` the schema, ask and agent endpoints take (omitted = the shared demo). */
export function withWorkspace(path: string, workspace?: number): string {
  return workspace === undefined ? path : `${path}${path.includes('?') ? '&' : '?'}workspace=${workspace}`
}
