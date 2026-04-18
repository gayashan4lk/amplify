import { getServerSession } from '@/lib/auth-server'
import Link from 'next/link'
import prisma from '@/lib/prisma'

export default async function DashboardPage() {
	const session = await getServerSession()

	if (!session) {
		return null
	}

	const data = await prisma.conversation.findMany({
		where: {
			userId: session.user.id,
		},
		orderBy: {
			updatedAt: 'desc',
		},
	})

	return (
		<div className="mx-auto max-w-3xl px-6 py-8">
			<div className="mb-6 flex items-center justify-between">
				<h1 className="text-xl font-semibold">Conversations</h1>
				<Link
					href="/chat"
					className="bg-foreground text-background rounded px-3 py-1.5 text-sm"
				>
					New chat
				</Link>
			</div>

			{data.length === 0 ? (
				<p className="text-muted-foreground text-sm">
					No prior conversations yet. Start one from the chat page.
				</p>
			) : (
				<ul className="space-y-2">
					{data.map((c) => (
						<li key={c.id}>
							<Link
								href={`/chat/${c.id}`}
								className="hover:bg-muted flex items-center justify-between rounded border px-4 py-3"
							>
								<div className="min-w-0 flex-1">
									<div className="truncate font-medium">{c.title}</div>
									<div className="text-muted-foreground text-xs">
										Updated{' '}
										{c.updatedAt.toLocaleString('en-GB', {
											dateStyle: 'short',
											timeStyle: 'short',
										})}
									</div>
								</div>
							</Link>
						</li>
					))}
				</ul>
			)}
		</div>
	)
}
