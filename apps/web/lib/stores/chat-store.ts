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

export type ActivityEntry =
	| { kind: 'agent_start'; agent: AgentName; at: number }
	| { kind: 'agent_end'; agent: AgentName; at: number }
	| { kind: 'progress'; phase: ProgressPhase; message: string; at: number }

export type StoredMessage =
	| { kind: 'user'; id: string; content: string }
	| { kind: 'assistant_text'; id: string; content: string }
	| { kind: 'assistant_brief'; id: string; brief: IntelligenceBrief }
	| { kind: 'activity_log'; id: string; entries: ActivityEntry[] }
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
	activityEntries: ActivityEntry[]
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
	activityEntries: [],
})

function flushActivityLog(
	messages: StoredMessage[],
	entries: ActivityEntry[],
	idHint: string,
): StoredMessage[] {
	if (entries.length === 0) return messages
	return [
		...messages,
		{ kind: 'activity_log', id: `activity_${idHint}`, entries },
	]
}

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
			// Each new user message kicks off a fresh SSE stream whose event ids
			// restart at 1. Clear the seen-id set so those ids don't collide with
			// the previous stream's and get dropped as duplicates.
			seenEventIds: new Set<string>(),
			stream: emptyStream(),
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
				const entry: ActivityEntry = { kind: 'agent_start', agent: ev.agent, at: Date.now() }
				set({
					stream: {
						...state.stream,
						activeAgent: ev.agent,
						activityEntries: [...state.stream.activityEntries, entry],
					},
					seenEventIds: seen,
				})
				return
			}
			case 'agent_end': {
				const endingAgent = state.stream.activeAgent
				const entries = endingAgent
					? [...state.stream.activityEntries, { kind: 'agent_end', agent: endingAgent, at: Date.now() } as ActivityEntry]
					: state.stream.activityEntries
				set({
					stream: { ...state.stream, activeAgent: null, activityEntries: entries },
					seenEventIds: seen,
				})
				return
			}
			case 'progress': {
				const entry: ActivityEntry = {
					kind: 'progress',
					phase: ev.phase,
					message: ev.message,
					at: Date.now(),
				}
				set({
					stream: {
						...state.stream,
						progress: { phase: ev.phase, message: ev.message },
						activityEntries: [...state.stream.activityEntries, entry],
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
					const flushed = flushActivityLog(
						state.messages,
						state.stream.activityEntries,
						ev.message_id,
					)
					set({
						messages: [
							...flushed,
							{ kind: 'assistant_brief', id: ev.message_id, brief },
						],
						stream: { ...state.stream, activityEntries: [] },
						seenEventIds: seen,
					})
				} else if (ev.component_type === 'clarification_poll') {
					const component = ev.component as {
						research_request_id: string
						prompt: string
						options: string[]
					}
					// LangGraph re-runs the clarification node on resume, so the
					// same clarification_poll custom event is dispatched twice
					// within one SSE stream. Drop the duplicate here so the UI
					// only ever renders one poll per research_request_id.
					const alreadyPresent = state.messages.some(
						(m) =>
							m.kind === 'assistant_clarification' &&
							m.research_request_id === component.research_request_id,
					)
					if (alreadyPresent) {
						set({ seenEventIds: seen })
					} else {
						const flushed = flushActivityLog(
							state.messages,
							state.stream.activityEntries,
							ev.message_id,
						)
						set({
							messages: [
								...flushed,
								{
									kind: 'assistant_clarification',
									id: ev.message_id,
									research_request_id: component.research_request_id,
									prompt: component.prompt,
									options: component.options,
									answered: false,
								},
							],
							stream: { ...state.stream, activityEntries: [] },
							seenEventIds: seen,
						})
					}
				}
				return
			}
			case 'error': {
				const flushed = flushActivityLog(
					state.messages,
					state.stream.activityEntries,
					eventId,
				)
				set({
					messages: [
						...flushed,
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
				const withActivity = flushActivityLog(
					state.messages,
					state.stream.activityEntries,
					eventId,
				)
				set({
					messages: [...withActivity, ...extraMessages],
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
