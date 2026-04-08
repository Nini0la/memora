import { FormEvent, useMemo, useState } from 'react'

type AuthMode = 'signup' | 'login'

type User = {
  id?: number
  email: string
  name?: string | null
  study_goal?: string | null
  preferred_recall_mode?: string
  created_at?: string
}

type AuthState = {
  accessToken: string
  user: User
}

type SavedNote = {
  id: number
  title: string | null
  raw_text: string
}

const STORAGE_KEY = 'memora-auth'
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

function loadAuth(): AuthState | null {
  const raw = localStorage.getItem(STORAGE_KEY)
  if (!raw) {
    return null
  }

  try {
    return JSON.parse(raw) as AuthState
  } catch {
    localStorage.removeItem(STORAGE_KEY)
    return null
  }
}

function persistAuth(auth: AuthState | null): void {
  if (!auth) {
    localStorage.removeItem(STORAGE_KEY)
    return
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(auth))
}

export default function App() {
  const [auth, setAuth] = useState<AuthState | null>(() => loadAuth())
  const [mode, setMode] = useState<AuthMode>('signup')
  const [busy, setBusy] = useState(false)
  const [authError, setAuthError] = useState('')

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [name, setName] = useState('')

  const [title, setTitle] = useState('')
  const [rawText, setRawText] = useState('')
  const [noteError, setNoteError] = useState('')
  const [savedNote, setSavedNote] = useState<SavedNote | null>(null)

  const authButtonLabel = useMemo(() => (mode === 'signup' ? 'Sign Up' : 'Log In'), [mode])

  async function handleAuthSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setAuthError('')
    setBusy(true)

    const endpoint = mode === 'signup' ? '/auth/signup' : '/auth/login'
    const payload =
      mode === 'signup'
        ? { email, password, name: name || null }
        : { email, password }

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })

      if (!response.ok) {
        throw new Error(`Auth failed with ${response.status}`)
      }

      const body = (await response.json()) as {
        access_token: string
        user: User
      }

      const nextAuth: AuthState = {
        accessToken: body.access_token,
        user: body.user,
      }
      persistAuth(nextAuth)
      setAuth(nextAuth)
    } catch {
      setAuthError('Authentication failed. Confirm your credentials and try again.')
    } finally {
      setBusy(false)
    }
  }

  async function handlePasteSave(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    if (!auth) {
      return
    }

    setNoteError('')
    setSavedNote(null)

    try {
      const response = await fetch(`${API_BASE_URL}/notes`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${auth.accessToken}`,
        },
        body: JSON.stringify({
          title,
          raw_text: rawText,
        }),
      })

      if (!response.ok) {
        throw new Error(`Note save failed with ${response.status}`)
      }

      const body = (await response.json()) as SavedNote
      setSavedNote(body)
      setRawText('')
      setTitle('')
    } catch {
      setNoteError('Could not save note. Check input and backend availability.')
    }
  }

  function logout() {
    persistAuth(null)
    setAuth(null)
    setSavedNote(null)
    setNoteError('')
  }

  if (!auth) {
    return (
      <main className="screen auth-screen">
        <section className="auth-panel">
          <p className="eyebrow">Recall Training Engine</p>
          <h1>Memora</h1>
          <p className="subtitle">Train retrieval strength with structured repetition.</p>

          <form className="auth-form" onSubmit={handleAuthSubmit}>
            {mode === 'signup' && (
              <label>
                Name
                <input value={name} onChange={(event) => setName(event.target.value)} />
              </label>
            )}

            <label>
              Email
              <input
                type="email"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                required
              />
            </label>

            <label>
              Password
              <input
                type="password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>

            <button type="submit" disabled={busy}>
              {authButtonLabel}
            </button>
          </form>

          {mode === 'signup' ? (
            <button
              type="button"
              className="mode-switch"
              onClick={() => setMode('login')}
              disabled={busy}
            >
              Use Login Instead
            </button>
          ) : (
            <button
              type="button"
              className="mode-switch"
              onClick={() => setMode('signup')}
              disabled={busy}
            >
              Use Sign Up Instead
            </button>
          )}

          {authError && <p role="alert">{authError}</p>}
        </section>
      </main>
    )
  }

  return (
    <main className="screen workspace-screen">
      <section className="workspace-header">
        <h1>Notes Workspace</h1>
        <p className="subtitle">Signed in as {auth.user.email}</p>
        <button type="button" className="logout" onClick={logout}>
          Log Out
        </button>
      </section>

      <section className="workspace-card">
        <h2>Paste Notes</h2>
        <form onSubmit={handlePasteSave} className="note-form">
          <label>
            Note Title
            <input
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              placeholder="e.g. Lecture 1"
            />
          </label>

          <label>
            Paste Note
            <textarea
              value={rawText}
              onChange={(event) => setRawText(event.target.value)}
              rows={8}
              required
            />
          </label>

          <button type="submit">Save Pasted Note</button>
        </form>

        {savedNote && <p>Saved note: {savedNote.title ?? 'Untitled'}</p>}
        {noteError && <p role="alert">{noteError}</p>}
      </section>
    </main>
  )
}
