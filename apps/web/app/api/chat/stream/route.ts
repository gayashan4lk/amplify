// Thin proxy that lets a browser `EventSource` connect to the FastAPI
// `POST /api/v1/chat/stream` endpoint. EventSource only speaks GET, so we
// accept a GET here with the message in query params, resolve the
// authenticated BetterAuth session, and forward the body to FastAPI with
// the session-scoped X-User-Id header.

import { NextRequest } from 'next/server'

import { requireUserId } from '@/lib/auth-server'

const FASTAPI_INTERNAL_URL = process.env.FASTAPI_INTERNAL_URL ?? 'http://localhost:8000'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
	const userId = await requireUserId()
	const url = new URL(req.url)
	const message = url.searchParams.get('message') ?? ''
	const conversationId = url.searchParams.get('conversation_id')

	const upstream = await fetch(`${FASTAPI_INTERNAL_URL}/api/v1/chat/stream`, {
		method: 'POST',
		headers: {
			'Content-Type': 'application/json',
			Accept: 'text/event-stream',
			'X-User-Id': userId,
		},
		body: JSON.stringify({ conversation_id: conversationId, message }),
	})

	return new Response(upstream.body, {
		status: upstream.status,
		headers: {
			'Content-Type': 'text/event-stream',
			'Cache-Control': 'no-cache',
			Connection: 'keep-alive',
			'X-Accel-Buffering': 'no',
		},
	})
}
