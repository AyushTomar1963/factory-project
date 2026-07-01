import { useCallback, useState } from "react"
import { login as loginRequest } from "../api/auth"
import { STORAGE_KEYS } from "../constants/inspection"

function readStoredAuth() {
  return {
    token: localStorage.getItem(STORAGE_KEYS.token) || "",
    role: localStorage.getItem(STORAGE_KEYS.role) || "",
    username: localStorage.getItem(STORAGE_KEYS.user) || "",
  }
}

export function useAuth() {
  const [auth, setAuth] = useState(readStoredAuth)
  const [authError, setAuthError] = useState("")
  const [isAuthenticating, setIsAuthenticating] = useState(false)

  const login = useCallback(async (username, password) => {
    setAuthError("")
    setIsAuthenticating(true)
    try {
      const data = await loginRequest(username.trim(), password)
      localStorage.setItem(STORAGE_KEYS.token, data.access_token)
      localStorage.setItem(STORAGE_KEYS.role, data.role)
      localStorage.setItem(STORAGE_KEYS.user, data.username)
      setAuth({
        token: data.access_token,
        role: data.role,
        username: data.username,
      })
      return true
    } catch (err) {
      setAuthError(err.message || "Authentication failed")
      return false
    } finally {
      setIsAuthenticating(false)
    }
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(STORAGE_KEYS.token)
    localStorage.removeItem(STORAGE_KEYS.role)
    localStorage.removeItem(STORAGE_KEYS.user)
    setAuth({ token: "", role: "", username: "" })
  }, [])

  return {
    ...auth,
    isAuthenticated: Boolean(auth.token),
    isAdmin: auth.role === "admin",
    authError,
    isAuthenticating,
    login,
    logout,
    clearAuthError: () => setAuthError(""),
  }
}
