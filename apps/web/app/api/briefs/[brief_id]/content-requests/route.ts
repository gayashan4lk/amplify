// Proxy for GET /api/v1/briefs/{brief_id}/content-requests — rehydration.

import { NextRequest, NextResponse } from 'next/server'

import { requireUserId } from '@/lib/auth-server'

const FASTAPI_INTERNAL_URL = process.env.FASTAPI_INTERNAL_URL ?? 'http://localhost:8000'

export const runtime = 'nodejs'

export async function GET(
	_req: NextRequest,
	{ params }: { params: Promise<{ brief_id: string }> },
) {
	const userId = await requireUserId()
	const { brief_id } = await params

	const upstream = await fetch(
		`${FASTAPI_INTERNAL_URL}/api/v1/briefs/${encodeURIComponent(brief_id)}/content-requests`,
		{ method: 'GET', headers: { 'X-User-Id': userId } },
	)

	const json = await upstream.json().catch(() => ({}))
	return NextResponse.json(json, { status: upstream.status })
}
