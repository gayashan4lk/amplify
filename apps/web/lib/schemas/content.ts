// Zod mirror of apps/api/models/content.py (T015).
//
// Canonical source: apps/api/models/content.py (Pydantic v2).
// Kept in sync at build time by the Pydantic -> Zod generator pipeline
// established in Stage 1. sse-client.ts validates every incoming payload
// before it reaches the store.
//
// See specs/002-content-generation/contracts/content-generation-request.md.

import { z } from 'zod'

export const HalfStatusSchema = z.enum(['pending', 'ready', 'failed'])
export type HalfStatus = z.infer<typeof HalfStatusSchema>

export const RequestStatusSchema = z.enum([
	'suggesting',
	'awaiting_input',
	'generating',
	'complete',
	'failed',
])
export type RequestStatus = z.infer<typeof RequestStatusSchema>

export const VariantLabelSchema = z.enum(['A', 'B'])
export type VariantLabel = z.infer<typeof VariantLabelSchema>

export const PostSuggestionSchema = z.object({
	id: z.string(),
	text: z.string().min(1).max(140),
	finding_ids: z.array(z.string()).min(1),
	low_confidence: z.boolean().default(false),
})
export type PostSuggestion = z.infer<typeof PostSuggestionSchema>

export const PostVariantSchema = z.object({
	label: VariantLabelSchema,
	description: z.string().min(80).max(250),
	description_status: HalfStatusSchema,
	image_key: z.string().nullable().optional(),
	image_signed_url: z.string().nullable().optional(),
	image_width: z.literal(1080),
	image_height: z.literal(1080),
	image_status: HalfStatusSchema,
	regenerations_used: z.number().int().min(0).max(3),
	source_suggestion_id: z.string().nullable().optional(),
	generation_trace_id: z.string(),
	updated_at: z.string(),
})
export type PostVariant = z.infer<typeof PostVariantSchema>

export const ContentGenerationRequestSchema = z
	.object({
		id: z.string(),
		brief_id: z.string(),
		conversation_id: z.string(),
		user_id: z.string(),
		status: RequestStatusSchema,
		suggestions: z.array(PostSuggestionSchema).max(4),
		user_direction: z.string().nullable().optional(),
		variants: z.array(PostVariantSchema).max(2),
		diversity_warning: z.boolean(),
		started_at: z.string(),
		completed_at: z.string().nullable().optional(),
		error_ref: z.string().nullable().optional(),
		schema_version: z.literal(1),
	})
	.refine((req) => req.suggestions.length !== 1, {
		message: 'suggestions length must be 0 or 2-4, never exactly 1',
		path: ['suggestions'],
	})
export type ContentGenerationRequest = z.infer<typeof ContentGenerationRequestSchema>

// Ephemeral-UI payload schemas (mirrors apps/api/models/ephemeral.py).
export const ContentSuggestionsListPayloadSchema = z.object({
	request_id: z.string(),
	suggestions: z.array(PostSuggestionSchema).max(4),
	question: z.string(),
})
export type ContentSuggestionsListPayload = z.infer<typeof ContentSuggestionsListPayloadSchema>

export const ContentVariantGridPayloadSchema = z.object({
	request_id: z.string(),
	variants: z.array(PostVariantSchema).max(2),
	diversity_warning: z.boolean(),
	regeneration_caps: z.record(VariantLabelSchema, z.number().int().min(0).max(3)).optional(),
})
export type ContentVariantGridPayload = z.infer<typeof ContentVariantGridPayloadSchema>
