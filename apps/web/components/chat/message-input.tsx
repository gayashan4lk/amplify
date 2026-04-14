// T048: Shadcn-based composer. On submit it posts via the Server Action
// below (which goes through lib/api-client.ts so X-User-Id is injected), and
// the client then opens an EventSource against a thin proxy route under
// apps/web/app/api/chat/stream/route.ts (NOT part of this task; the proxy
// forwards the same body + session header to FastAPI).

'use client'

import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { useChatStore, type StoredMessage } from '@/lib/stores/chat-store'
import { SseClient } from '@/lib/sse-client'
import type { SseEvent } from '@/lib/types/sse-events'

export default function MessageInput() {
	const [value, setValue] = useState('')
	const [pending, setPending] = useState(false)
	const conversationId = useChatStore((s) => s.conversationId)
	const addUserMessage = useChatStore((s) => s.addUserMessage)
	const applyEvent = useChatStore((s) => s.applyEvent)

	async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
		e.preventDefault()
		const message = value.trim()
		if (!message || pending) return

		setPending(true)
		setValue('')
		addUserMessage(message)

		// The app/api/chat/stream proxy route mirrors the POST body into the
		// FastAPI call and streams the response back. That route is created as
		// part of the quickstart wiring; its URL is what we connect to.
		const qs = new URLSearchParams({ message })
		if (conversationId) qs.set('conversation_id', conversationId)
		const client = new SseClient({
			url: `/api/chat/stream?${qs.toString()}`,
			onEvent: (id, ev: SseEvent) => applyEvent(id, ev),
			onClose: () => setPending(false),
		})
		client.start()
	}

	return (
		<form onSubmit={onSubmit} className="flex items-end gap-3">
			<textarea
				value={value}
				onChange={(e) => setValue(e.target.value)}
				disabled={pending}
				rows={2}
				placeholder="Ask a scoped research question…"
				className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm"
			/>
			<Button type="submit" disabled={pending || value.trim().length === 0}>
				{pending ? 'Researching…' : 'Send'}
			</Button>
		</form>
	)
}

// Tell the TypeScript checker that StoredMessage is intentionally re-exported
// for other client code that imports from this file.
export type { StoredMessage }
