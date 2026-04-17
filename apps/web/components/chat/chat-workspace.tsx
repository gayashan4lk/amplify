// Client-side container that mounts the chat store, the SSE client, and the
// three render components (message list + composer + status badge). Server
// components hand it the initial message list.

'use client'

import { useEffect } from 'react'

import MessageInput from '@/components/chat/message-input'
import MessageList from '@/components/chat/message-list'
import { SseClient } from '@/lib/sse-client'
import { useChatStore, type StoredMessage } from '@/lib/stores/chat-store'

type Props = {
	conversationId: string | null
	initialMessages: StoredMessage[]
	latestStatus?: 'complete' | 'pending' | 'failed'
}

export default function ChatWorkspace({
	conversationId,
	initialMessages,
	latestStatus,
}: Props) {
	const loadInitial = useChatStore((s) => s.loadInitial)
	const applyEvent = useChatStore((s) => s.applyEvent)

	useEffect(() => {
		loadInitial(initialMessages, conversationId)
	}, [initialMessages, conversationId, loadInitial])

	// T066: if the stored status is `pending`, a prior stream was in-flight.
	// Reopen a reconnect SSE stream so the user sees the completion instead of
	// a stuck UI. Completed/failed conversations render only the stored state.
	useEffect(() => {
		if (!conversationId || latestStatus !== 'pending') return
		const client = new SseClient({
			url: `/api/chat/stream?conversation_id=${conversationId}&reconnect=1`,
			onEvent: (id, ev) => applyEvent(id, ev),
		})
		client.start()
		return () => client.close()
	}, [conversationId, latestStatus, applyEvent])

	return (
		<div className="flex h-full flex-col">
			<div className="flex-1 overflow-y-auto px-6 py-4">
				<MessageList />
			</div>
			<div className="border-t px-6 py-4">
				<MessageInput />
			</div>
		</div>
	)
}
