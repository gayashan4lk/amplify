// T044: authenticated dashboard shell. Redirects to /login when there is no
// BetterAuth session. Wraps /chat and /conversations.

import { redirect } from 'next/navigation'

import { getServerSession } from '@/lib/auth-server'

export default async function DashboardLayout({
	children,
}: {
	children: React.ReactNode
}) {
	const session = await getServerSession()
	if (!session?.user?.id) {
		redirect('/login')
	}

	return (
		<div className="flex h-full min-h-screen flex-col">
			<header className="flex items-center justify-between border-b px-6 py-3">
				<div className="font-semibold">Amplify</div>
				<div className="text-xs text-muted-foreground">{session.user.email}</div>
			</header>
			<main className="flex-1">{children}</main>
		</div>
	)
}
