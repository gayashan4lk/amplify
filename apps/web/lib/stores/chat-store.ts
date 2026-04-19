// T046: Zustand store holding the message list, streaming buffer, seen ids.
//
// The chat page SSR-hydrates prior messages through `loadInitial`, and
// `sse-client.ts` feeds incoming events via `applyEvent`. De-duplication is
// enforced by `seenEventIds` — the SSE wire format assigns monotonically
// increasing ids per stream, and we drop any we've already processed so that
// reconnects with Last-Event-ID don't double-render.

import { create } from 'zustand'

import type {
	ContentSuggestionsListPayload,
	ContentVariantGridPayload,
	PostSuggestion,
	PostVariant,
	VariantLabel,
} from '@/lib/schemas/content'
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
			kind: 'assistant_content_suggestions'
			id: string
			request_id: string
			question: string
			suggestions: PostSuggestion[]
	  }
	| {
			kind: 'assistant_content_variants'
			id: string
			request_id: string
			variants: PostVariant[]
			diversity_warning: boolean
			regeneration_caps: Partial<Record<VariantLabel, number>>
			progress: Partial<Record<VariantLabel, { step: string; progress_hint?: number | null }>>
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
		{ kind: 'activity_log', id: `activity_${idHint}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`, entries },
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
					const alreadyPresent = state.messages.some((m) => m.id === ev.message_id)
					const flushed = flushActivityLog(
						state.messages,
						state.stream.activityEntries,
						ev.message_id,
					)
					set({
						messages: alreadyPresent
							? flushed
							: [
									...flushed,
									{ kind: 'assistant_brief', id: ev.message_id, brief },
								],
						stream: { ...state.stream, activityEntries: [] },
						seenEventIds: seen,
					})
				} else if (ev.component_type === 'content_suggestions') {
					const payload = ev.component as ContentSuggestionsListPayload
					const alreadyPresent = state.messages.some((m) => m.id === ev.message_id)
					const flushed = flushActivityLog(
						state.messages,
						state.stream.activityEntries,
						ev.message_id,
					)
					set({
						messages: alreadyPresent
							? flushed
							: [
									...flushed,
									{
										kind: 'assistant_content_suggestions',
										id: ev.message_id,
										request_id: payload.request_id,
										question: payload.question,
										suggestions: payload.suggestions,
									},
								],
						stream: { ...state.stream, activityEntries: [] },
						seenEventIds: seen,
					})
				} else if (ev.component_type === 'content_variant_grid') {
					const payload = ev.component as ContentVariantGridPayload
					const alreadyPresent = state.messages.some((m) => m.id === ev.message_id)
					const flushed = flushActivityLog(
						state.messages,
						state.stream.activityEntries,
						ev.message_id,
					)
					set({
						messages: alreadyPresent
							? flushed
							: [
									...flushed,
									{
										kind: 'assistant_content_variants',
										id: ev.message_id,
										request_id: payload.request_id,
										variants: payload.variants,
										diversity_warning: payload.diversity_warning,
										regeneration_caps: payload.regeneration_caps ?? {},
										progress: {},
									},
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
			case 'content_suggestions': {
				const alreadyPresent = state.messages.some((m) => m.id === ev.message_id)
				const flushed = flushActivityLog(
					state.messages,
					state.stream.activityEntries,
					ev.message_id,
				)
				set({
					messages: alreadyPresent
						? flushed
						: [
								...flushed,
								{
									kind: 'assistant_content_suggestions',
									id: ev.message_id,
									request_id: ev.request_id,
									question: ev.question,
									suggestions: ev.suggestions,
								},
							],
					stream: { ...state.stream, activityEntries: [] },
					seenEventIds: seen,
				})
				return
			}
			case 'content_variant_progress': {
				const messages = state.messages.map((m) =>
					m.kind === 'assistant_content_variants' && m.request_id === ev.request_id
						? {
								...m,
								progress: {
									...m.progress,
									[ev.variant_label]: {
										step: ev.step,
										progress_hint: ev.progress_hint ?? null,
									},
								},
							}
						: m,
				)
				set({ messages, seenEventIds: seen })
				return
			}
			case 'content_variant_ready': {
				const messages = state.messages.map((m) => {
					if (
						m.kind !== 'assistant_content_variants' ||
						m.request_id !== ev.request_id
					) {
						return m
					}
					const others = m.variants.filter((v) => v.label !== ev.variant.label)
					const progress = { ...m.progress }
					delete progress[ev.variant.label]
					const regeneration_caps = {
						...m.regeneration_caps,
						[ev.variant.label]: Math.max(0, 3 - ev.variant.regenerations_used),
					}
					return {
						...m,
						variants: [...others, ev.variant],
						progress,
						regeneration_caps,
					}
				})
				set({ messages, seenEventIds: seen })
				return
			}
			case 'content_variant_partial': {
				const messages = state.messages.map((m) => {
					if (
						m.kind !== 'assistant_content_variants' ||
						m.request_id !== ev.request_id
					) {
						return m
					}
					const others = m.variants.filter((v) => v.label !== ev.variant_label)
					const existing = m.variants.find((v) => v.label === ev.variant_label)
					const merged: PostVariant = {
						label: ev.variant_label,
						description: ev.description ?? existing?.description ?? '',
						description_status: ev.description_status,
						image_key: existing?.image_key ?? null,
						image_signed_url: ev.image_signed_url ?? existing?.image_signed_url ?? null,
						image_width: 1080,
						image_height: 1080,
						image_status: ev.image_status,
						regenerations_used: existing?.regenerations_used ?? 0,
						source_suggestion_id: existing?.source_suggestion_id ?? null,
						generation_trace_id: existing?.generation_trace_id ?? '',
						updated_at: existing?.updated_at ?? new Date().toISOString(),
					}
					return { ...m, variants: [...others, merged] }
				})
				set({ messages, seenEventIds: seen })
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
				const existingIds = new Set(state.messages.map((m) => m.id))
				const buffered = Object.entries(state.stream.textBufferByMessageId)
				const extraMessages: StoredMessage[] = buffered
					.filter(([id]) => !existingIds.has(id))
					.map(([id, content]) => ({
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
