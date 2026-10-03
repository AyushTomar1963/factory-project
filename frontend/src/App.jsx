import { BrowserRouter, Navigate, Route, Routes, useNavigate } from "react-router-dom"
import { AdminDashboardPage } from "./pages/AdminDashboardPage"
import { LoginPage } from "./pages/LoginPage"
import { StorePage } from "./pages/StorePage"
import { WorkerPage } from "./pages/WorkerPage"
import { AppBackground } from "./components/effects/AppBackground"
import { useAuth } from "./hooks/useAuth"

function HomeRedirect({ auth }) {
  if (auth.isStoreKeeper) return <Navigate to="/store" replace />
  if (auth.isAdmin) return <Navigate to="/admin" replace />
  return <WorkerPage token={auth.token} onLogout={auth.logout} />
}

function AppRoutes({ auth }) {
  const navigate = useNavigate()

  const handleLogin = async (username, password) => {
    const success = await auth.login(username, password)
    if (success) navigate("/", { replace: true })
    return success
  }

  const handleLogout = () => {
    auth.logout()
    navigate("/", { replace: true })
  }

  if (!auth.isAuthenticated) {
    return (
      <LoginPage
        onLogin={handleLogin}
        authError={auth.authError}
        isAuthenticating={auth.isAuthenticating}
      />
    )
  }

  return (
    <Routes>
      <Route
        path="/store"
        element={
          auth.isStoreKeeper || auth.isAdmin ? (
            <StorePage
              token={auth.token}
              username={auth.username}
              onLogout={handleLogout}
            />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route
        path="/admin"
        element={
          auth.isAdmin ? (
            <AdminDashboardPage
              token={auth.token}
              username={auth.username}
              onLogout={handleLogout}
            />
          ) : (
            <Navigate to="/" replace />
          )
        }
      />
      <Route path="/" element={<HomeRedirect auth={{ ...auth, logout: handleLogout }} />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  )
}

export default function App() {
  const auth = useAuth()

  return (
    <BrowserRouter>
      <div className="relative min-h-svh overflow-x-hidden">
        <AppBackground />
        <div className="relative z-10">
          <AppRoutes auth={auth} />
        </div>
      </div>
    </BrowserRouter>
  )
}
