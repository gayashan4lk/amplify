// Proxy for POST /api/v1/chat/ephemeral — resolves the authenticated session
// and forwards the clarification response to FastAPI with X-User-Id set.

import { NextRequest, NextResponse } from 'next/server'

import { requireUserId } from '@/lib/auth-server'

const FASTAPI_INTERNAL_URL = process.env.FASTAPI_INTERNAL_URL ?? 'http://localhost:8000'

export const runtime = 'nodejs'

export async function POST(req: NextRequest) {
	const userId = await requireUserId()
	const body = (await req.json()) as {
		research_request_id: string
		component_type: 'clarification_poll'
		response: { selected_option_index: number }
	}

	// Server-side resolution of the active conversation is out of scope for
	// this proxy — the FastAPI endpoint derives it from the research request.
	const upstream = await fetch(`${FASTAPI_INTERNAL_URL}/api/v1/chat/ephemeral`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'X-User-Id': userId },
		body: JSON.stringify({
			conversation_id: '',
			research_request_id: body.research_request_id,
			component_type: body.component_type,
			response: body.response,
		}),
	})

	const json = await upstream.json().catch(() => ({}))
	return NextResponse.json(json, { status: upstream.status })
}
