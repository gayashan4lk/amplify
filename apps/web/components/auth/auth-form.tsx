'use client'

import Link from 'next/link'
import { useRouter } from 'next/navigation'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { authClient } from '@/lib/auth-client'

type Mode = 'login' | 'signup'

export function AuthForm({ mode }: { mode: Mode }) {
	const router = useRouter()
	const [email, setEmail] = useState('')
	const [password, setPassword] = useState('')
	const [name, setName] = useState('')
	const [error, setError] = useState<string | null>(null)
	const [loading, setLoading] = useState(false)

	async function handleEmail(e: React.FormEvent) {
		e.preventDefault()
		setError(null)
		setLoading(true)
		try {
			if (mode === 'signup') {
				const { error } = await authClient.signUp.email({
					email,
					password,
					name: name || email.split('@')[0],
				})
				if (error) throw new Error(error.message ?? 'signup failed')
			} else {
				const { error } = await authClient.signIn.email({ email, password })
				if (error) throw new Error(error.message ?? 'login failed')
			}
			router.push('/')
			router.refresh()
		} catch (err) {
			setError(err instanceof Error ? err.message : 'unknown error')
		} finally {
			setLoading(false)
		}
	}

	async function handleSocial(provider: 'github' | 'google') {
		setError(null)
		try {
			await authClient.signIn.social({ provider, callbackURL: '/' })
		} catch (err) {
			setError(err instanceof Error ? err.message : 'oauth error')
		}
	}

	const submitLabel = mode === 'login' ? 'Login' : 'Sign up'
	const altHref = mode === 'login' ? '/signup' : '/signin'
	const altLabel =
		mode === 'login'
			? "Don't have an account? Sign up"
			: 'Already have an account? Login'

	return (
		<div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 py-12">
			<div className="flex flex-row justify-center">
				<h1 className="mb-6 text-3xl font-black">Amplify</h1>
			</div>

			<div className="mb-4 flex flex-col gap-2">
				<Button
					type="button"
					variant="outline"
					onClick={() => handleSocial('github')}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						width="16"
						height="16"
						fill="currentColor"
						className="bi bi-github antialiased"
						viewBox="0 0 16 16"
					>
						<path
							d="M8 0C3.58 0 0 3.58 0 8c0 3.54 2.29 6.53 5.47 7.59.4.07.55-.17.55-.38 0-.19-.01-.82-.01-1.49-2.01.37-2.53-.49-2.69-.94-.09-.23-.48-.94-.82-1.13-.28-.15-.68-.52-.01-.53.63-.01 1.08.58 1.23.82.72 1.21 1.87.87 2.33.66.07-.52.28-.87.51-1.07-1.78-.2-3.64-.89-3.64-3.95 0-.87.31-1.59.82-2.15-.08-.2-.36-1.02.08-2.12 0 0 .67-.21 2.2.82.64-.18 1.32-.27 2-.27s1.36.09 2 .27c1.53-1.04 2.2-.82 2.2-.82.44 1.1.16 1.92.08 2.12.51.56.82 1.27.82 2.15 0 3.07-1.87 3.75-3.65 3.95.29.25.54.73.54 1.48 0 1.07-.01 1.93-.01 2.2 0 .21.15.46.55.38A8.01 8.01 0 0 0 16 8c0-4.42-3.58-8-8-8"
							fill="currentColor"
						/>
					</svg>
					{submitLabel} with GitHub
				</Button>
				<Button
					type="button"
					variant="outline"
					onClick={() => handleSocial('google')}
				>
					<svg
						xmlns="http://www.w3.org/2000/svg"
						width="16"
						height="16"
						fill="currentColor"
						className="bi bi-google"
						viewBox="0 0 16 16"
					>
						<path
							d="M15.545 6.558a9.4 9.4 0 0 1 .139 1.626c0 2.434-.87 4.492-2.384 5.885h.002C11.978 15.292 10.158 16 8 16A8 8 0 1 1 8 0a7.7 7.7 0 0 1 5.352 2.082l-2.284 2.284A4.35 4.35 0 0 0 8 3.166c-2.087 0-3.86 1.408-4.492 3.304a4.8 4.8 0 0 0 0 3.063h.003c.635 1.893 2.405 3.301 4.492 3.301 1.078 0 2.004-.276 2.722-.764h-.003a3.7 3.7 0 0 0 1.599-2.431H8v-3.08z"
							fill="currentColor"
						/>
					</svg>
					{submitLabel} with Google
				</Button>
			</div>

			<div className="text-muted-foreground my-4 flex items-center gap-3 text-xs">
				<div className="bg-border h-px flex-1" />
				or continue with
				<div className="bg-border h-px flex-1" />
			</div>

			<form onSubmit={handleEmail} className="flex flex-col gap-3">
				{mode === 'signup' && (
					<label className="flex flex-col gap-1 text-sm">
						Name
						<input
							className="border-border bg-background h-9 rounded-md border px-3 text-sm"
							value={name}
							onChange={(e) => setName(e.target.value)}
							autoComplete="name"
						/>
					</label>
				)}
				<label className="flex flex-col gap-1 text-sm">
					Email
					<input
						type="email"
						required
						className="border-border bg-background h-9 rounded-md border px-3 text-sm"
						value={email}
						onChange={(e) => setEmail(e.target.value)}
						autoComplete="email"
					/>
				</label>
				<label className="flex flex-col gap-1 text-sm">
					Password
					<input
						type="password"
						required
						minLength={8}
						className="border-border bg-background h-9 rounded-md border px-3 text-sm"
						value={password}
						onChange={(e) => setPassword(e.target.value)}
						autoComplete={
							mode === 'login' ? 'current-password' : 'new-password'
						}
					/>
				</label>
				{error && <p className="text-destructive text-sm">{error}</p>}
				<Button type="submit" disabled={loading}>
					{loading ? '…' : submitLabel}
				</Button>
			</form>

			<Link
				href={altHref}
				className="text-muted-foreground mt-4 text-center text-sm hover:underline"
			>
				{altLabel}
			</Link>
		</div>
	)
}
