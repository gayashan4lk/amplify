// T049: renders the full StoredMessage list plus the in-flight stream buffer
// via <StreamRenderer />.

'use client'

import StreamRenderer from '@/components/chat/stream-renderer'
import ClarificationPoll from '@/components/ephemeral/clarification-poll'
import IntelligenceBrief from '@/components/ephemeral/intelligence-brief'
import FailureCard from '@/components/chat/failure-card'
import { useChatStore } from '@/lib/stores/chat-store'
import { SseClient } from '@/lib/sse-client'
import type { SseEvent } from '@/lib/types/sse-events'

export default function MessageList() {
	const messages = useChatStore((s) => s.messages)
	const conversationId = useChatStore((s) => s.conversationId)
	const addUserMessage = useChatStore((s) => s.addUserMessage)
	const applyEvent = useChatStore((s) => s.applyEvent)

	const lastUserMessage = [...messages]
		.reverse()
		.find((m): m is Extract<typeof messages[number], { kind: 'user' }> => m.kind === 'user')

	function handleRetry() {
		if (!lastUserMessage) return
		const content = lastUserMessage.content
		addUserMessage(content)
		const qs = new URLSearchParams({ message: content })
		if (conversationId) qs.set('conversation_id', conversationId)
		const client = new SseClient({
			url: `/api/chat/stream?${qs.toString()}`,
			onEvent: (id, ev: SseEvent) => applyEvent(id, ev),
		})
		client.start()
	}

	return (
		<ol className="flex flex-col gap-4">
			{messages.map((m) => {
				switch (m.kind) {
					case 'user':
						return (
							<li key={m.id} className="self-end max-w-xl rounded-md bg-muted px-4 py-2">
								{m.content}
							</li>
						)
					case 'assistant_text':
						return (
							<li key={m.id} className="self-start max-w-xl">
								<p className="text-sm leading-6">{m.content}</p>
							</li>
						)
					case 'assistant_brief':
						return (
							<li key={m.id} className="self-stretch">
								<IntelligenceBrief brief={m.brief} />
							</li>
						)
					case 'assistant_clarification':
						return (
							<li key={m.id} className="self-stretch">
								<ClarificationPoll
									messageId={m.id}
									researchRequestId={m.research_request_id}
									prompt={m.prompt}
									options={m.options}
									answered={m.answered}
								/>
							</li>
						)
					case 'failure':
						return (
							<li key={m.id} className="self-stretch">
								<FailureCard
									code={m.code}
									message={m.message}
									recoverable={m.recoverable}
									suggestedAction={m.suggested_action ?? null}
									onRetry={lastUserMessage ? handleRetry : undefined}
								/>
							</li>
						)
				}
			})}
			<StreamRenderer />
		</ol>
	)
}
