// T046: Zustand store holding the message list, streaming buffer, seen ids.
//
// The chat page SSR-hydrates prior messages through `loadInitial`, and
// `sse-client.ts` feeds incoming events via `applyEvent`. De-duplication is
// enforced by `seenEventIds` — the SSE wire format assigns monotonically
// increasing ids per stream, and we drop any we've already processed so that
// reconnects with Last-Event-ID don't double-render.

import { create } from 'zustand'

import type { IntelligenceBrief, SseEvent } from '@/lib/types/sse-events'

export type AgentName = 'supervisor' | 'research' | 'clarification'
export type ProgressPhase = 'planning' | 'searching' | 'synthesizing' | 'validating'

export type StoredMessage =
	| { kind: 'user'; id: string; content: string }
	| { kind: 'assistant_text'; id: string; content: string }
	| { kind: 'assistant_brief'; id: string; brief: IntelligenceBrief }
	| {
			kind: 'assistant_clarification'
			id: string
			research_request_id: string
			prompt: string
			options: string[]
			answered: boolean
	  }
	| {
			kind: 'failure'
			id: string
			code: string
			message: string
			recoverable: boolean
			suggested_action?: string | null
			failure_record_id: string
			trace_id?: string | null
	  }

export type StreamState = {
	activeAgent: AgentName | null
	progress: { phase: ProgressPhase; message: string } | null
	textBufferByMessageId: Record<string, string>
}

type ChatState = {
	conversationId: string | null
	messages: StoredMessage[]
	stream: StreamState
	seenEventIds: Set<string>
	setConversationId: (id: string) => void
	loadInitial: (msgs: StoredMessage[], conversationId: string | null) => void
	addUserMessage: (content: string) => void
	applyEvent: (eventId: string, ev: SseEvent) => void
	resetStream: () => void
}

const emptyStream = (): StreamState => ({
	activeAgent: null,
	progress: null,
	textBufferByMessageId: {},
})

export const useChatStore = create<ChatState>((set, get) => ({
	conversationId: null,
	messages: [],
	stream: emptyStream(),
	seenEventIds: new Set<string>(),

	setConversationId: (id) => set({ conversationId: id }),

	loadInitial: (msgs, conversationId) =>
		set({
			messages: msgs,
			conversationId,
			stream: emptyStream(),
			seenEventIds: new Set(),
		}),

	addUserMessage: (content) =>
		set((s) => ({
			messages: [
				...s.messages,
				{ kind: 'user', id: `u_${Date.now()}`, content },
			],
		})),

	applyEvent: (eventId, ev) => {
		const state = get()
		if (state.seenEventIds.has(eventId)) return
		const seen = new Set(state.seenEventIds)
		seen.add(eventId)

		switch (ev.type) {
			case 'conversation_ready': {
				set({ conversationId: ev.conversation_id, seenEventIds: seen })
				return
			}
			case 'agent_start': {
				set({
					stream: { ...state.stream, activeAgent: ev.agent },
					seenEventIds: seen,
				})
				return
			}
			case 'agent_end': {
				set({
					stream: { ...state.stream, activeAgent: null },
					seenEventIds: seen,
				})
				return
			}
			case 'progress': {
				set({
					stream: {
						...state.stream,
						progress: { phase: ev.phase, message: ev.message },
					},
					seenEventIds: seen,
				})
				return
			}
			case 'text_delta': {
				const prev = state.stream.textBufferByMessageId[ev.message_id] ?? ''
				set({
					stream: {
						...state.stream,
						textBufferByMessageId: {
							...state.stream.textBufferByMessageId,
							[ev.message_id]: prev + ev.delta,
						},
					},
					seenEventIds: seen,
				})
				return
			}
			case 'ephemeral_ui': {
				if (ev.component_type === 'intelligence_brief') {
					const brief = ev.component as IntelligenceBrief
					set({
						messages: [
							...state.messages,
							{ kind: 'assistant_brief', id: ev.message_id, brief },
						],
						seenEventIds: seen,
					})
				} else if (ev.component_type === 'clarification_poll') {
					const component = ev.component as {
						research_request_id: string
						prompt: string
						options: string[]
					}
					set({
						messages: [
							...state.messages,
							{
								kind: 'assistant_clarification',
								id: ev.message_id,
								research_request_id: component.research_request_id,
								prompt: component.prompt,
								options: component.options,
								answered: false,
							},
						],
						seenEventIds: seen,
					})
				}
				return
			}
			case 'error': {
				set({
					messages: [
						...state.messages,
						{
							kind: 'failure',
							id: eventId,
							code: ev.code,
							message: ev.message,
							recoverable: ev.recoverable,
							suggested_action: ev.suggested_action ?? null,
							failure_record_id: ev.failure_record_id,
							trace_id: ev.trace_id ?? null,
						},
					],
					stream: emptyStream(),
					seenEventIds: seen,
				})
				return
			}
			case 'done': {
				// flush any buffered text delta to a message
				const buffered = Object.entries(state.stream.textBufferByMessageId)
				const extraMessages: StoredMessage[] = buffered.map(([id, content]) => ({
					kind: 'assistant_text',
					id,
					content,
				}))
				set({
					messages: [...state.messages, ...extraMessages],
					stream: emptyStream(),
					seenEventIds: seen,
				})
				return
			}
			default: {
				set({ seenEventIds: seen })
			}
		}
	},

	resetStream: () => set({ stream: emptyStream() }),
}))
