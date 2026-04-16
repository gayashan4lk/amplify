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
			router.push('/chat')
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
			await authClient.signIn.social({ provider, callbackURL: '/chat' })
		} catch (err) {
			setError(err instanceof Error ? err.message : 'oauth error')
		}
	}

	const title = mode === 'login' ? 'Sign in to Amplify' : 'Create your account'
	const submitLabel = mode === 'login' ? 'Sign in' : 'Sign up'
	const altHref = mode === 'login' ? '/signup' : '/login'
	const altLabel = mode === 'login' ? "Don't have an account? Sign up" : 'Already have an account? Sign in'

	return (
		<div className="mx-auto flex min-h-screen max-w-sm flex-col justify-center px-6 py-12">
			<h1 className="mb-6 text-2xl font-semibold">{title}</h1>

			<div className="mb-4 flex flex-col gap-2">
				<Button type="button" variant="outline" onClick={() => handleSocial('github')}>
					Continue with GitHub
				</Button>
				<Button type="button" variant="outline" onClick={() => handleSocial('google')}>
					Continue with Google
				</Button>
			</div>

			<div className="my-4 flex items-center gap-3 text-xs text-muted-foreground">
				<div className="h-px flex-1 bg-border" />
				or
				<div className="h-px flex-1 bg-border" />
			</div>

			<form onSubmit={handleEmail} className="flex flex-col gap-3">
				{mode === 'signup' && (
					<label className="flex flex-col gap-1 text-sm">
						Name
						<input
							className="h-9 rounded-md border border-border bg-background px-3 text-sm"
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
						className="h-9 rounded-md border border-border bg-background px-3 text-sm"
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
						className="h-9 rounded-md border border-border bg-background px-3 text-sm"
						value={password}
						onChange={(e) => setPassword(e.target.value)}
						autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
					/>
				</label>
				{error && <p className="text-sm text-destructive">{error}</p>}
				<Button type="submit" disabled={loading}>
					{loading ? '…' : submitLabel}
				</Button>
			</form>

			<Link href={altHref} className="mt-4 text-center text-sm text-muted-foreground hover:underline">
				{altLabel}
			</Link>
		</div>
	)
}
