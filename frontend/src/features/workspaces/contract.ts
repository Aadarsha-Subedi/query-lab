// Kept free of imports so a root-level test can check it against the backend source.
/** The column types the API accepts (backend/workspaces/naming.py COLUMN_TYPES; a test keeps them equal). */
export const COLUMN_TYPES = ['text', 'integer', 'bigint', 'numeric', 'boolean', 'date', 'timestamp'] as const
export const ON_DELETE = ['NO ACTION', 'CASCADE'] as const
