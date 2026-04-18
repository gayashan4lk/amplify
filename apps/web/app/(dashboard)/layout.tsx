// T044: authenticated dashboard shell. Redirects to /login when there is no
// BetterAuth session. Wraps /chat and /conversations.

import { redirect } from 'next/navigation'

import { getServerSession } from '@/lib/auth-server'
import { Button } from '@/components/ui/button'
import { signOut } from '@/actions/auth'
import Link from 'next/link'

export default async function DashboardLayout({
	children,
}: {
	children: React.ReactNode
}) {
	const session = await getServerSession()
	if (!session?.user?.id) {
		return (
			<div>
				<h1 className="text-6xl font-bold">Amplify</h1>
				<Link className="text-blue-500 hover:underline" href="/signin">
					Login
				</Link>{' '}
				or{' '}
				<Link className="text-blue-500 hover:underline" href="/signup">
					Signup
				</Link>
			</div>
		)
	}

	return (
		<div className="flex h-full min-h-screen flex-col">
			<header className="flex items-center justify-between border-b px-6 py-3">
				<Link href="/">
					<h1 className="font-semibold">Amplify</h1>
				</Link>
				<div>
					<Button onClick={signOut}>Logout</Button>
					<div className="text-muted-foreground text-xs">
						{session.user.email}
					</div>
				</div>
			</header>
			<main className="flex-1">{children}</main>
		</div>
	)
}
