// Proxy for GET /api/v1/content/stream?request_id=... — SSE passthrough.

import { NextRequest } from 'next/server'

import { requireUserId } from '@/lib/auth-server'

const FASTAPI_INTERNAL_URL = process.env.FASTAPI_INTERNAL_URL ?? 'http://localhost:8000'

export const runtime = 'nodejs'
export const dynamic = 'force-dynamic'

export async function GET(req: NextRequest) {
	const userId = await requireUserId()
	const url = new URL(req.url)
	const requestId = url.searchParams.get('request_id') ?? ''

	const upstream = await fetch(
		`${FASTAPI_INTERNAL_URL}/api/v1/content/stream?request_id=${encodeURIComponent(requestId)}`,
		{
			method: 'GET',
			headers: { Accept: 'text/event-stream', 'X-User-Id': userId },
		},
	)

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
