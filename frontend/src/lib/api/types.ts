import type { components } from './schema.gen'

/** A response or request schema from backend/openapi.json, by name: `Schema<'AgentLimitsOut'>`. */
export type Schema<Name extends keyof components['schemas']> = components['schemas'][Name]
