import { useEffect, useState } from "react"
import { createUser, fetchUsers } from "../../api/admin"
import { Button } from "../ui/qa-button"
import { FormField, Input, Select } from "../ui/FormField"
import { AlertBanner } from "../ui/StatusBadge"
import { SectionCard } from "./AdminAppShell"

function RoleBadge({ role }) {
  const styles =
    role === "admin"
      ? "bg-brand-100 text-brand-800"
      : "bg-green-100 text-green-700"
  return (
    <span className={`px-3 py-1 rounded-full text-xs font-bold capitalize ${styles}`}>
      {role}
    </span>
  )
}

export function UsersPanel({ token }) {
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [message, setMessage] = useState("")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [role, setRole] = useState("worker")
  const [isSaving, setIsSaving] = useState(false)
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let cancelled = false

    fetchUsers(token)
      .then((data) => {
        if (!cancelled) setUsers(data)
      })
      .catch((err) => {
        if (!cancelled) setError(err.message)
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => {
      cancelled = true
    }
  }, [token, reloadKey])

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    setIsSaving(true)
    setError("")
    setMessage("")
    try {
      const result = await createUser(token, {
        username: username.trim(),
        password,
        role,
      })
      setMessage(result.message)
      setUsername("")
      setPassword("")
      setRole("worker")
      setReloadKey((key) => key + 1)
    } catch (err) {
      setError(err.message)
    } finally {
      setIsSaving(false)
    }
  }

  return (
    <div className="space-y-6">
      {error && <AlertBanner tone="error">{error}</AlertBanner>}
      {message && <AlertBanner tone="info">{message}</AlertBanner>}

      <SectionCard
        title="Station accounts"
        description="Workers use the QC portal; admins manage master data and dashboards."
      >
        {loading ? (
          <p className="text-gray-500 font-semibold">Loading users...</p>
        ) : (
          <div className="overflow-x-auto -mx-6">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="bg-gray-50 text-xs text-gray-500 uppercase border-y border-gray-200">
                  <th className="p-4 font-bold">Username</th>
                  <th className="p-4 font-bold">Role</th>
                </tr>
              </thead>
              <tbody>
                {users.map((user) => (
                  <tr key={user.username} className="border-b border-gray-100">
                    <td className="p-4 font-mono font-semibold">{user.username}</td>
                    <td className="p-4">
                      <RoleBadge role={user.role} />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </SectionCard>

      <SectionCard title="Create account">
        <form onSubmit={handleSubmit} className="space-y-4 max-w-lg">
          <FormField label="Username" htmlFor="new-username">
            <Input
              id="new-username"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              placeholder="e.g. floor_worker_1"
              autoComplete="off"
              required
            />
          </FormField>
          <FormField label="Password" htmlFor="new-password">
            <Input
              id="new-password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="new-password"
              required
            />
          </FormField>
          <FormField label="Role" htmlFor="new-role">
            <Select id="new-role" value={role} onChange={(e) => setRole(e.target.value)}>
              <option value="worker">Worker (floor inspections)</option>
              <option value="admin">Admin (master data + dashboard)</option>
            </Select>
          </FormField>
          <Button type="submit" variant="gradient" size="sm" disabled={isSaving}>
            {isSaving ? "Creating..." : "Create user"}
          </Button>
        </form>
      </SectionCard>
    </div>
  )
}
