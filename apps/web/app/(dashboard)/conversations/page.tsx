// T064: SSR-fetched list of the current user's conversations. Each row
// links to /chat/[id] and shows the title, updated-at, and latest status
// badge derived by the FastAPI list endpoint.

import Link from 'next/link'

import { apiJson } from '@/lib/api-client'

type ConversationRow = {
	id: string
	title: string
	created_at: string
	updated_at: string
	latest_status: 'complete' | 'pending' | 'failed'
}

type ListResponse = {
	conversations: ConversationRow[]
	next_cursor: string | null
}

function formatUpdated(iso: string): string {
	try {
		return new Date(iso).toLocaleString()
	} catch {
		return iso
	}
}

function StatusBadge({ status }: { status: ConversationRow['latest_status'] }) {
	const color =
		status === 'complete'
			? 'bg-emerald-100 text-emerald-900'
			: status === 'failed'
				? 'bg-rose-100 text-rose-900'
				: 'bg-amber-100 text-amber-900'
	return (
		<span className={`rounded px-2 py-0.5 text-xs font-medium ${color}`}>
			{status}
		</span>
	)
}

export default async function ConversationsListPage() {
	let data: ListResponse
	try {
		data = await apiJson<ListResponse>('/api/v1/conversations')
	} catch {
		data = { conversations: [], next_cursor: null }
	}

	return (
		<div className="mx-auto max-w-3xl px-6 py-8">
			<div className="mb-6 flex items-center justify-between">
				<h1 className="text-xl font-semibold">Conversations</h1>
				<Link
					href="/chat"
					className="rounded bg-foreground px-3 py-1.5 text-sm text-background"
				>
					New research
				</Link>
			</div>

			{data.conversations.length === 0 ? (
				<p className="text-sm text-muted-foreground">
					No prior conversations yet. Start one from the chat page.
				</p>
			) : (
				<ul className="space-y-2">
					{data.conversations.map((c) => (
						<li key={c.id}>
							<Link
								href={`/chat/${c.id}`}
								className="flex items-center justify-between rounded border px-4 py-3 hover:bg-muted"
							>
								<div className="min-w-0 flex-1">
									<div className="truncate font-medium">{c.title}</div>
									<div className="text-xs text-muted-foreground">
										Updated {formatUpdated(c.updated_at)}
									</div>
								</div>
								<StatusBadge status={c.latest_status} />
							</Link>
						</li>
					))}
				</ul>
			)}
		</div>
	)
}
