import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
import { Toaster } from 'sonner'
import App from '@/App'
import { AuthProvider } from '@/contexts/AuthContext'
import '@/index.css'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
        <Toaster
          position="bottom-right"
          toastOptions={{ classNames: { toast: 'border-zinc-200! text-zinc-900! font-sans!' } }}
        />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
