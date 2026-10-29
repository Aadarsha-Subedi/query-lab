import { render, screen } from '@testing-library/react'

import { App } from './App'
import { EnvErrorScreen } from './EnvErrorScreen'

describe('app shell', () => {
  it('renders the app name', () => {
    render(<App env={{ VITE_API_BASE_URL: 'http://localhost:5173', VITE_APP_NAME: 'Querylab' }} />)
    expect(screen.getByRole('heading', { name: 'Querylab' })).toBeInTheDocument()
  })

  it('shows the hard error screen for a broken env', () => {
    render(<EnvErrorScreen problems={['VITE_APP_NAME: Required']} />)
    expect(screen.getByRole('alert')).toHaveTextContent('VITE_APP_NAME: Required')
  })
})
