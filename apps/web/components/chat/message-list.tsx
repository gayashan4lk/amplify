// T049: renders the full StoredMessage list plus the in-flight stream buffer
// via <StreamRenderer />.

'use client'

import { useState } from 'react'
import Markdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import StreamRenderer from '@/components/chat/stream-renderer'
import ClarificationPoll from '@/components/ephemeral/clarification-poll'
import ContentSuggestionsList from '@/components/ephemeral/content-suggestions'
import ContentVariantGrid from '@/components/ephemeral/content-variant-grid'
import IntelligenceBrief from '@/components/ephemeral/intelligence-brief'
import FailureCard from '@/components/chat/failure-card'
import { useChatStore } from '@/lib/stores/chat-store'
import { SseClient } from '@/lib/sse-client'
import type { VariantLabel } from '@/lib/schemas/content'
import type { SseEvent } from '@/lib/types/sse-events'
import AgentStatus from "./agent-status"

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

	const [regeneratingByRequest, setRegeneratingByRequest] = useState<
		Record<string, VariantLabel | null>
	>({})

	async function handleRegenerate(
		requestId: string,
		args: { label: VariantLabel; additionalGuidance: string },
	) {
		const { label, additionalGuidance } = args
		if (regeneratingByRequest[requestId]) return
		setRegeneratingByRequest((prev) => ({ ...prev, [requestId]: label }))
		try {
			const resp = await fetch(`/api/v1/content/${requestId}/regenerate`, {
				method: 'POST',
				credentials: 'include',
				headers: { 'content-type': 'application/json' },
				body: JSON.stringify({
					label,
					additional_guidance: additionalGuidance || null,
				}),
			})
			if (!resp.ok) {
				// 202/409/404: nothing to stream. Caps/state stay as-is.
				return
			}
			const data = (await resp.json()) as {
				sse_endpoint: string
				regenerations_used: number
			}
			const client = new SseClient({
				url: data.sse_endpoint,
				onEvent: (id, ev: SseEvent) => applyEvent(id, ev),
				onClose: () =>
					setRegeneratingByRequest((prev) => ({ ...prev, [requestId]: null })),
			})
			client.start()
		} catch {
			setRegeneratingByRequest((prev) => ({ ...prev, [requestId]: null }))
		}
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
							<li key={m.id} className="self-start max-w-2xl">
								<div className="prose prose-sm max-w-none text-sm leading-6 [&_p]:my-2 [&_ul]:my-2 [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:my-2 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-0.5 [&_strong]:font-semibold [&_h1]:mt-3 [&_h1]:mb-2 [&_h1]:text-base [&_h1]:font-semibold [&_h2]:mt-3 [&_h2]:mb-2 [&_h2]:text-base [&_h2]:font-semibold [&_h3]:mt-3 [&_h3]:mb-1 [&_h3]:text-sm [&_h3]:font-semibold [&_code]:rounded [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:text-xs [&_pre]:my-2 [&_pre]:overflow-x-auto [&_pre]:rounded [&_pre]:bg-muted [&_pre]:p-3 [&_a]:underline [&_a]:underline-offset-2">
									<Markdown remarkPlugins={[remarkGfm]}>{m.content}</Markdown>
								</div>
							</li>
						)
					case 'activity_log':
						return (
							<li key={m.id} className="self-stretch rounded-md border border-dashed px-4 py-3 text-muted-foreground">
								<div className="text-xs uppercase tracking-wide">activity</div>
								<ul className="mt-2 space-y-1 text-sm">
									{m.entries.map((e, i) => (
										<li key={i}>
											{e.kind === 'agent_start' && <>{e.agent} started</>}
											{e.kind === 'agent_end' && <>{e.agent} finished</>}
											{e.kind === 'progress' && (
												<>
													<span className="font-medium">{e.phase}:</span> {e.message}
												</>
											)}
										</li>
									))}
								</ul>
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
					case 'assistant_content_suggestions':
						return (
							<li key={m.id} className="self-stretch">
								<ContentSuggestionsList
									requestId={m.request_id}
									question={m.question}
									suggestions={m.suggestions}
								/>
							</li>
						)
					case 'assistant_content_variants':
						return (
							<li key={m.id} className="self-stretch">
								<ContentVariantGrid
									requestId={m.request_id}
									variants={m.variants}
									diversityWarning={m.diversity_warning}
									progress={m.progress}
									regenerationCaps={m.regeneration_caps}
									regeneratingLabel={regeneratingByRequest[m.request_id] ?? null}
									onRegenerate={(args) => handleRegenerate(m.request_id, args)}
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
									traceId={m.trace_id ?? null}
									onRetry={lastUserMessage ? handleRetry : undefined}
								/>
							</li>
						)
				}
			})}
			<AgentStatus />
			<StreamRenderer />
		</ol>
	)
}
