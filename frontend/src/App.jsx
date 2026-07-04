import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
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

export default function App() {
  const auth = useAuth()

  return (
    <BrowserRouter>
      <div className="relative min-h-svh overflow-x-hidden">
        <AppBackground />
        <div className="relative z-10">
          {!auth.isAuthenticated ? (
            <LoginPage
              onLogin={auth.login}
              authError={auth.authError}
              isAuthenticating={auth.isAuthenticating}
            />
          ) : (
            <Routes>
              <Route
                path="/store"
                element={
                  auth.isStoreKeeper || auth.isAdmin ? (
                    <StorePage
                      token={auth.token}
                      username={auth.username}
                      onLogout={auth.logout}
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
                      onLogout={auth.logout}
                    />
                  ) : (
                    <Navigate to="/" replace />
                  )
                }
              />
              <Route path="/" element={<HomeRedirect auth={auth} />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          )}
        </div>
      </div>
    </BrowserRouter>
  )
}
