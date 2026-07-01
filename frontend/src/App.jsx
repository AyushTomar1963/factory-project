import { AdminDashboardPage } from "./pages/AdminDashboardPage"
import { LoginPage } from "./pages/LoginPage"
import { WorkerPage } from "./pages/WorkerPage"
import { AppBackground } from "./components/effects/AppBackground"
import { useAuth } from "./hooks/useAuth"

export default function App() {
  const auth = useAuth()

  const page = !auth.isAuthenticated ? (
    <LoginPage
      onLogin={auth.login}
      authError={auth.authError}
      isAuthenticating={auth.isAuthenticating}
    />
  ) : auth.isAdmin ? (
    <AdminDashboardPage
      token={auth.token}
      username={auth.username}
      onLogout={auth.logout}
    />
  ) : (
    <WorkerPage token={auth.token} onLogout={auth.logout} />
  )

  return (
    <div className="relative min-h-svh">
      <AppBackground />
      <div className="relative z-10">{page}</div>
    </div>
  )
}
