// T045: SSR shell that loads prior messages for an existing conversation
// and hydrates the chat store before handing control to the client workspace.

import { notFound } from 'next/navigation'

import ChatWorkspace from '@/components/chat/chat-workspace'
import { apiJson } from '@/lib/api-client'
import type { StoredMessage } from '@/lib/stores/chat-store'

type ConversationDetailResponse = {
	id: string
	title: string
	created_at: string
	updated_at: string
	latest_status: 'complete' | 'pending' | 'failed'
	messages: Array<{
		id: string
		role: 'user' | 'system' | 'assistant'
		content: string
		brief: unknown | null
		failure: {
			id: string
			code: string
			user_message: string
			suggested_action: string | null
			recoverable: boolean
		} | null
	}>
}

export default async function ConversationPage({
	params,
}: {
	params: Promise<{ conversationId: string }>
}) {
	const { conversationId } = await params

	let detail: ConversationDetailResponse
	try {
		detail = await apiJson<ConversationDetailResponse>(
			`/api/v1/conversations/${conversationId}`,
		)
	} catch {
		notFound()
	}

	const initialMessages: StoredMessage[] = detail.messages.map((m) => {
		if (m.brief) {
			return {
				kind: 'assistant_brief',
				id: m.id,
				// biome-ignore lint/suspicious/noExplicitAny: trusted server payload
				brief: m.brief as any,
			}
		}
		if (m.failure) {
			return {
				kind: 'failure',
				id: m.id,
				code: m.failure.code,
				message: m.failure.user_message,
				recoverable: m.failure.recoverable,
				suggested_action: m.failure.suggested_action,
				failure_record_id: m.failure.id,
			}
		}
		if (m.role === 'user') {
			return { kind: 'user', id: m.id, content: m.content }
		}
		return { kind: 'assistant_text', id: m.id, content: m.content }
	})

	return (
		<ChatWorkspace
			conversationId={conversationId}
			initialMessages={initialMessages}
			latestStatus={detail.latest_status}
		/>
	)
}
