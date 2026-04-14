// -----------------------------------------------------------------------------
// SSE event Zod schemas + inferred TypeScript types.
//
// Canonical source: apps/api/sse/events.py (Pydantic) and
// specs/001-research-agent/contracts/sse-events.md.
//
// Kept in sync at build time by scripts/generate-sse-types.ts (T018).
// sse-client.ts (T047) validates every incoming payload with
// `SseEventSchema.safeParse` and drops payloads that fail or carry v != 1.
// -----------------------------------------------------------------------------

import { z } from 'zod'

const BaseEvent = z.object({
	v: z.literal(1),
	conversation_id: z.string(),
	at: z.string(), // ISO 8601
})

const AgentName = z.enum(['supervisor', 'research', 'clarification'])
const Confidence = z.enum(['high', 'medium', 'low'])
const SourceType = z.enum([
	'news',
	'blog',
	'forum',
	'competitor_site',
	'official',
	'ad_library',
	'analytics',
	'other',
])

const SourceAttributionSchema = z.object({
	title: z.string().min(1).max(300),
	url: z.string().url(),
	source_type: SourceType,
	consulted_at: z.string(),
	accessible: z.boolean().default(true),
	snippet: z.string().max(500).nullable().optional(),
})

const FindingSchema = z.object({
	id: z.string(),
	rank: z.number().int().min(1),
	claim: z.string().min(1).max(280),
	evidence: z.string().min(1).max(1200),
	confidence: Confidence,
	sources: z.array(SourceAttributionSchema),
	contradicts: z.array(z.string()).default([]),
	unsourced: z.boolean().default(false),
	notes: z.string().max(500).nullable().optional(),
})

export const IntelligenceBriefSchema = z.object({
	id: z.string(),
	v: z.literal(1),
	user_id: z.string(),
	conversation_id: z.string(),
	research_request_id: z.string(),
	scoped_question: z.string().min(1).max(1000),
	status: z.enum(['complete', 'low_confidence']),
	findings: z.array(FindingSchema).min(1),
	generated_at: z.string(),
	model_used: z.string(),
	trace_id: z.string().nullable().optional(),
})

export const ClarificationPollSchema = z.object({
	research_request_id: z.string(),
	prompt: z.string(),
	options: z.array(z.string()).min(3).max(4),
})

const ConversationReadySchema = BaseEvent.extend({
	type: z.literal('conversation_ready'),
	is_new: z.boolean(),
})

const AgentStartSchema = BaseEvent.extend({
	type: z.literal('agent_start'),
	agent: AgentName,
	description: z.string(),
})

const AgentEndSchema = BaseEvent.extend({
	type: z.literal('agent_end'),
	agent: AgentName,
})

const ToolCallSchema = BaseEvent.extend({
	type: z.literal('tool_call'),
	tool: z.string(),
	input: z.record(z.string(), z.unknown()),
})

const ToolResultSchema = BaseEvent.extend({
	type: z.literal('tool_result'),
	tool: z.string(),
	result_count: z.number().int(),
	duration_ms: z.number().int(),
})

const ProgressSchema = BaseEvent.extend({
	type: z.literal('progress'),
	phase: z.enum(['planning', 'searching', 'synthesizing', 'validating']),
	message: z.string(),
	detail: z.record(z.string(), z.unknown()).nullable().optional(),
})

const TextDeltaSchema = BaseEvent.extend({
	type: z.literal('text_delta'),
	message_id: z.string(),
	delta: z.string(),
})

const EphemeralUISchema = BaseEvent.extend({
	type: z.literal('ephemeral_ui'),
	message_id: z.string(),
	component_type: z.enum(['intelligence_brief', 'clarification_poll']),
	component: z.unknown(),
})

const ErrorSchema = BaseEvent.extend({
	type: z.literal('error'),
	code: z.enum([
		'tavily_unavailable',
		'tavily_rate_limited',
		'llm_unavailable',
		'llm_invalid_output',
		'no_findings_above_threshold',
		'user_cancelled',
		'budget_exceeded',
		'rate_limited_user',
	]),
	message: z.string().min(1),
	recoverable: z.boolean(),
	suggested_action: z.string().nullable().optional(),
	failure_record_id: z.string(),
})

const DoneSchema = BaseEvent.extend({
	type: z.literal('done'),
	final_status: z.enum(['brief_ready', 'text_only', 'awaiting_clarification']),
	summary: z.string().nullable().optional(),
})

export const SseEventSchema = z.discriminatedUnion('type', [
	ConversationReadySchema,
	AgentStartSchema,
	AgentEndSchema,
	ToolCallSchema,
	ToolResultSchema,
	ProgressSchema,
	TextDeltaSchema,
	EphemeralUISchema,
	ErrorSchema,
	DoneSchema,
])

export type SseEvent = z.infer<typeof SseEventSchema>
export type IntelligenceBrief = z.infer<typeof IntelligenceBriefSchema>
export type ClarificationPoll = z.infer<typeof ClarificationPollSchema>
export type Finding = z.infer<typeof FindingSchema>
export type SourceAttribution = z.infer<typeof SourceAttributionSchema>
