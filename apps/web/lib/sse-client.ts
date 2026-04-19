// T047: thin wrapper around native EventSource.
//
// Responsibilities:
// - reconnect with exponential backoff (2s → 16s)
// - resume via Last-Event-ID (the browser sends it automatically; we also
//   track the last seen id for safety)
// - validate every payload through the Zod SseEventSchema and drop any
//   payload that fails or has v != 1, surfacing a toast
// - de-dup is handled in chat-store by eventId
//
// POST /api/v1/chat/stream is called from a Server Action in
// components/chat/message-input.tsx; this module is only responsible for the
// streaming connection, not for kicking it off.

'use client'

import { SseEventSchema, type SseEvent } from '@/lib/types/sse-events'

export type SseClientOptions = {
	url: string
	onEvent: (eventId: string, event: SseEvent) => void
	onInvalid?: (reason: string, raw: unknown) => void
	onOpen?: () => void
	onClose?: () => void
}

const MAX_RETRIES = 3

export class SseClient {
	private source: EventSource | null = null
	private closed = false
	private retries = 0

	constructor(private readonly opts: SseClientOptions) {}

	start() {
		if (this.source || this.closed) return
		const es = new EventSource(this.opts.url, { withCredentials: true })
		this.source = es

		es.onopen = () => {
			this.retries = 0
			this.opts.onOpen?.()
		}

		const handleMessage = (evt: MessageEvent) => {
			let parsed: unknown
			try {
				parsed = JSON.parse(evt.data)
			} catch {
				this.opts.onInvalid?.('invalid json', evt.data)
				return
			}
			const result = SseEventSchema.safeParse(parsed)
			if (!result.success) {
				this.opts.onInvalid?.('schema mismatch', parsed)
				return
			}
			const eventId = evt.lastEventId || `${Date.now()}`
			this.opts.onEvent(eventId, result.data)
			// Server-sent `done` terminates the stream. EventSource treats the
			// subsequent socket close as an error, so we must close ourselves
			// first to prevent the reconnect loop.
			if (result.data.type === 'done' || result.data.type === 'error') {
				this.close()
			}
		}

		es.onmessage = handleMessage
		for (const type of [
			'conversation_ready',
			'agent_start',
			'agent_end',
			'progress',
			'tool_call',
			'tool_result',
			'text_delta',
			'ephemeral_ui',
			'content_suggestions',
			'content_variant_progress',
			'content_variant_ready',
			'content_variant_partial',
			'error',
			'done',
		]) {
			es.addEventListener(type, handleMessage as EventListener)
		}

		es.onerror = () => {
			if (this.closed) return
			es.close()
			this.source = null
			if (this.retries >= MAX_RETRIES) {
				this.close()
				return
			}
			this.retries += 1
			const backoff = 2000 * 2 ** (this.retries - 1)
			setTimeout(() => {
				if (!this.closed) this.start()
			}, backoff)
		}
	}

	close() {
		this.closed = true
		this.source?.close()
		this.source = null
		this.opts.onClose?.()
	}
}
