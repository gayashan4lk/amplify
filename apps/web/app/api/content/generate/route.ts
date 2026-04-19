// Proxy for POST /api/v1/content/generate.

import { NextRequest, NextResponse } from 'next/server'

import { requireUserId } from '@/lib/auth-server'

const FASTAPI_INTERNAL_URL = process.env.FASTAPI_INTERNAL_URL ?? 'http://localhost:8000'

export const runtime = 'nodejs'

export async function POST(req: NextRequest) {
	const userId = await requireUserId()
	const body = await req.json()

	const upstream = await fetch(`${FASTAPI_INTERNAL_URL}/api/v1/content/generate`, {
		method: 'POST',
		headers: { 'Content-Type': 'application/json', 'X-User-Id': userId },
		body: JSON.stringify(body),
	})

	const json = await upstream.json().catch(() => ({}))
	return NextResponse.json(json, { status: upstream.status })
}
