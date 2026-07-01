import { useState } from "react"
import { Eye, EyeOff, User } from "lucide-react"
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card"
import {
  Field,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { BrandLogo } from "../components/layout/Shell"
import { Button } from "../components/ui/qa-button"
import { Input } from "../components/ui/FormField"

const DEV_HINT = import.meta.env.DEV

export function LoginPage({ onLogin, authError, isAuthenticating }) {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password) return
    await onLogin(username, password)
  }

  const fillDemo = (role) => {
    if (role === "admin") {
      setUsername("admin")
      setPassword("admin123")
    } else {
      setUsername("worker")
      setPassword("worker123")
    }
  }

  return (
    <div className="flex min-h-svh flex-col items-center justify-center p-6">
      <div className="flex w-full max-w-sm flex-col gap-6">
        <div className="flex flex-col items-center gap-2 text-center">
          <BrandLogo size="lg" />
          <p className="font-semibold text-foreground">Rushab Industries</p>
        </div>

        <Card className="border-brand-100/80 bg-card/90 shadow-[var(--shadow-login)] backdrop-blur-md">
          <CardHeader className="text-center">
            <CardTitle className="text-xl">Factory QA Portal</CardTitle>
            <CardDescription>Sign in to your inspection station</CardDescription>
          </CardHeader>
          <CardContent>
            <form onSubmit={handleSubmit}>
              <FieldGroup className="gap-4">
                <Field>
                  <FieldLabel htmlFor="username">Username</FieldLabel>
                  <Input
                    id="username"
                    type="text"
                    required
                    placeholder="admin or worker"
                    value={username}
                    onChange={(e) => setUsername(e.target.value)}
                    autoComplete="username"
                  />
                </Field>
                <Field>
                  <FieldLabel htmlFor="password">Password</FieldLabel>
                  <div className="relative">
                    <Input
                      id="password"
                      type={showPassword ? "text" : "password"}
                      required
                      placeholder="Enter password"
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="pr-11"
                      autoComplete="current-password"
                    />
                    <button
                      type="button"
                      onClick={() => setShowPassword((prev) => !prev)}
                      className="absolute top-1/2 right-3 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                      aria-label={showPassword ? "Hide password" : "Show password"}
                    >
                      {showPassword ? (
                        <EyeOff className="size-4" />
                      ) : (
                        <Eye className="size-4" />
                      )}
                    </button>
                  </div>
                </Field>
                {authError && (
                  <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-center text-xs font-medium text-red-700">
                    {authError}
                  </p>
                )}
                <Button
                  type="submit"
                  variant="primary"
                  size="block"
                  disabled={isAuthenticating}
                  className="w-full"
                >
                  {isAuthenticating ? "Signing in…" : "Sign in"}
                </Button>
              </FieldGroup>
            </form>
          </CardContent>
        </Card>

        {DEV_HINT && (
          <div className="rounded-lg border border-dashed border-border bg-card p-3 text-center">
            <p className="mb-2 text-xs text-muted-foreground">Local demo accounts</p>
            <div className="flex justify-center gap-2">
              <button
                type="button"
                onClick={() => fillDemo("admin")}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-brand-700 hover:bg-brand-50"
              >
                <User className="size-3.5" />
                Admin
              </button>
              <button
                type="button"
                onClick={() => fillDemo("worker")}
                className="flex items-center gap-1 rounded-md px-2 py-1 text-xs font-semibold text-brand-700 hover:bg-brand-50"
              >
                <User className="size-3.5" />
                Worker
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
