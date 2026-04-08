import { fireEvent, render, screen, waitFor } from '@testing-library/react'

import App from '../App'

const API = 'http://localhost:8000'

afterEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

test('shows auth form when unauthenticated', () => {
  render(<App />)

  expect(screen.getByRole('heading', { name: /memora/i })).toBeInTheDocument()
  expect(screen.getByLabelText(/email/i)).toBeInTheDocument()
  expect(screen.getByLabelText(/password/i)).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /sign up/i })).toBeInTheDocument()
})

test('logs in and shows notes workspace', async () => {
  vi.spyOn(global, 'fetch').mockResolvedValueOnce(
    new Response(
      JSON.stringify({
        access_token: 'token-123',
        token_type: 'bearer',
        user: {
          id: 1,
          email: 'ada@example.com',
          name: 'Ada',
          study_goal: null,
          preferred_recall_mode: 'typing',
          created_at: '2026-04-07T00:00:00Z',
        },
      }),
      { status: 200, headers: { 'Content-Type': 'application/json' } },
    ),
  )

  render(<App />)

  fireEvent.click(screen.getByRole('button', { name: /use login instead/i }))
  fireEvent.change(screen.getByLabelText(/email/i), {
    target: { value: 'ada@example.com' },
  })
  fireEvent.change(screen.getByLabelText(/password/i), {
    target: { value: 'strong-password-123' },
  })

  fireEvent.click(screen.getByRole('button', { name: /^log in$/i }))

  await waitFor(() => {
    expect(screen.getByRole('heading', { name: /notes workspace/i })).toBeInTheDocument()
  })

  expect(localStorage.getItem('memora-auth')).toContain('token-123')
})

test('creates paste note with bearer auth', async () => {
  localStorage.setItem(
    'memora-auth',
    JSON.stringify({
      accessToken: 'token-abc',
      user: { email: 'ada@example.com', name: 'Ada' },
    }),
  )

  const fetchMock = vi.spyOn(global, 'fetch').mockResolvedValue(
    new Response(
      JSON.stringify({
        id: 10,
        user_id: 1,
        title: 'Lecture 1',
        raw_text: 'Distributed systems basics',
        source_type: 'paste',
        warning: null,
        processing_status: 'stored',
        created_at: '2026-04-07T00:00:00Z',
      }),
      { status: 201, headers: { 'Content-Type': 'application/json' } },
    ),
  )

  render(<App />)

  fireEvent.change(screen.getByLabelText(/note title/i), {
    target: { value: 'Lecture 1' },
  })
  fireEvent.change(screen.getByLabelText(/paste note/i), {
    target: { value: 'Distributed systems basics' },
  })

  fireEvent.click(screen.getByRole('button', { name: /save pasted note/i }))

  await waitFor(() => {
    expect(fetchMock).toHaveBeenCalledWith(`${API}/notes`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: 'Bearer token-abc',
      },
      body: JSON.stringify({
        title: 'Lecture 1',
        raw_text: 'Distributed systems basics',
      }),
    })
  })

  expect(screen.getByText(/saved note: lecture 1/i)).toBeInTheDocument()
})
