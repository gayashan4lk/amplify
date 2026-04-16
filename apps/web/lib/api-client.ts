import 'server-only'
import { requireUserId } from './auth-server'

const FASTAPI_INTERNAL_URL = process.env.FASTAPI_INTERNAL_URL ?? 'http://localhost:8000'

type ApiInit = Omit<RequestInit, 'headers'> & {
	headers?: Record<string, string>
}

export async function apiFetch(path: string, init: ApiInit = {}): Promise<Response> {
	if (typeof window !== 'undefined') {
		throw new Error('api-client must only run on the server — it injects X-User-Id from the session')
	}
	const userId = await requireUserId()
	const headers: Record<string, string> = {
		'Content-Type': 'application/json',
		...(init.headers ?? {}),
		'X-User-Id': userId,
	}
	return fetch(`${FASTAPI_INTERNAL_URL}${path}`, { ...init, headers })
}

export async function apiJson<T = unknown>(path: string, init: ApiInit = {}): Promise<T> {
	const resp = await apiFetch(path, init)
	if (!resp.ok) {
		const body = await resp.text()
		throw new Error(`api ${path} failed ${resp.status}: ${body}`)
	}
	return (await resp.json()) as T
}
