/** Shown instead of the app when `.env` is missing a variable. Plain markup on
 * purpose: it must render even when nothing else is configured. */
export function EnvErrorScreen({ problems }: { problems: string[] }) {
  return (
    <main role="alert" style={{ fontFamily: 'system-ui, sans-serif', padding: '2rem', maxWidth: '40rem' }}>
      <h1>Configuration error</h1>
      <p>The app cannot start because these environment variables are missing or invalid:</p>
      <ul>
        {problems.map((problem) => (
          <li key={problem}>
            <code>{problem}</code>
          </li>
        ))}
      </ul>
      <p>
        Copy <code>frontend/.env.example</code> to <code>frontend/.env</code>, fill it in and restart the dev
        server.
      </p>
    </main>
  )
}
