// Client-side container that mounts the chat store, the SSE client, and the
// three render components (message list + composer + status badge). Server
// components hand it the initial message list.

'use client'

import { useEffect } from 'react'

import MessageInput from '@/components/chat/message-input'
import MessageList from '@/components/chat/message-list'
import { SseClient } from '@/lib/sse-client'
import {
	ContentGenerationRequestSchema,
	type ContentGenerationRequest,
} from '@/lib/schemas/content'
import { useChatStore, type StoredMessage } from '@/lib/stores/chat-store'
import type { SseEvent } from '@/lib/types/sse-events'

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

	// T040: for each brief rendered in the loaded history, fetch prior
	// content-generation requests for that brief and re-emit them as
	// ephemeral `content_variant_grid` events so the variants + diversity
	// warning show up in the correct chronological slot.
	useEffect(() => {
		const briefMessages = initialMessages.filter(
			(m): m is Extract<StoredMessage, { kind: 'assistant_brief' }> =>
				m.kind === 'assistant_brief',
		)
		if (briefMessages.length === 0) return
		let cancelled = false

		void (async () => {
			for (const m of briefMessages) {
				try {
					const res = await fetch(
						`/api/briefs/${encodeURIComponent(m.brief.id)}/content-requests`,
					)
					if (!res.ok || cancelled) continue
					const data = (await res.json()) as {
						requests?: unknown[]
						regeneration_caps_by_request?: Record<string, Record<string, number>>
					}
					const requests = (data.requests ?? [])
						.map((r) => {
							const parsed = ContentGenerationRequestSchema.safeParse(r)
							return parsed.success ? parsed.data : null
						})
						.filter((r): r is ContentGenerationRequest => r !== null)
					for (const req of requests) {
						if (req.status !== 'complete' || req.variants.length === 0) continue
						const ev: SseEvent = {
							v: 1,
							type: 'ephemeral_ui',
							conversation_id: req.conversation_id,
							at: req.completed_at ?? req.started_at,
							message_id: `rehydrate_${req.id}`,
							component_type: 'content_variant_grid',
							component: {
								request_id: req.id,
								variants: req.variants,
								diversity_warning: req.diversity_warning,
								regeneration_caps:
									data.regeneration_caps_by_request?.[req.id] ?? {},
							},
						}
						applyEvent(`rehydrate_${req.id}`, ev)
					}
				} catch {
					// best effort rehydration
				}
			}
		})()

		return () => {
			cancelled = true
		}
	}, [initialMessages, applyEvent])

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
