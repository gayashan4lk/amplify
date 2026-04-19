// ContentSuggestionsList ephemeral component (T036).
//
// Renders 2-4 PostSuggestion chips with finding-id pills plus the
// consolidated creative-direction question, then a dedicated reply textbox
// that POSTs the direction to /api/content/{request_id}/direction.
//
// The spec envisioned routing the reply through the chat composer; for MVP
// we keep this self-contained so the suggestion card owns its own reply
// loop.

'use client'

import { useState } from 'react'

import { Button } from '@/components/ui/button'
import type { PostSuggestion } from '@/lib/schemas/content'

type Props = {
	requestId: string
	question: string
	suggestions: PostSuggestion[]
}

export default function ContentSuggestionsList({
	requestId,
	question,
	suggestions,
}: Props) {
	const [direction, setDirection] = useState('')
	const [pending, setPending] = useState(false)
	const [submitted, setSubmitted] = useState(false)
	const [error, setError] = useState<string | null>(null)

	async function onSubmit(e: React.FormEvent<HTMLFormElement>) {
		e.preventDefault()
		const trimmed = direction.trim()
		if (!trimmed || pending || submitted) return
		setPending(true)
		setError(null)
		try {
			const res = await fetch(`/api/content/${encodeURIComponent(requestId)}/direction`, {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({ user_direction: trimmed }),
			})
			if (!res.ok) {
				const data = await res.json().catch(() => ({}))
				setError(data?.error?.message ?? `Failed (${res.status})`)
				return
			}
			setSubmitted(true)
		} catch (err) {
			setError(err instanceof Error ? err.message : 'Network error')
		} finally {
			setPending(false)
		}
	}

	return (
		<div
			className="rounded-lg border bg-card p-5 shadow-sm"
			data-request-id={requestId}
			data-testid="content-suggestions-list"
		>
			<header className="mb-3">
				<div className="text-xs uppercase tracking-wide text-muted-foreground">
					Post angle suggestions
				</div>
			</header>

			<ul className="flex flex-col gap-2">
				{suggestions.map((s) => (
					<li
						key={s.id}
						className="rounded-md border p-3 text-sm"
					>
						<p className="leading-snug">{s.text}</p>
						<div className="mt-2 flex flex-wrap items-center gap-1">
							{s.finding_ids.map((id) => (
								<span
									key={id}
									className="rounded-full bg-muted px-2 py-0.5 text-xs text-muted-foreground"
								>
									finding {id}
								</span>
							))}
							{s.low_confidence && (
								<span className="rounded-full bg-yellow-100 px-2 py-0.5 text-xs text-yellow-800">
									low confidence
								</span>
							)}
						</div>
					</li>
				))}
			</ul>

			<p className="mt-4 rounded bg-muted/40 p-3 text-sm">
				<span className="font-medium">Direction: </span>
				{question}
			</p>

			{submitted ? (
				<p className="mt-3 text-sm text-green-700">
					Direction received — generating two Facebook variants…
				</p>
			) : (
				<form onSubmit={onSubmit} className="mt-3 flex items-end gap-2">
					<textarea
						value={direction}
						onChange={(e) => setDirection(e.target.value)}
						disabled={pending}
						rows={2}
						placeholder="Reply with your creative direction…"
						className="flex-1 resize-none rounded-md border bg-background px-3 py-2 text-sm"
						maxLength={2000}
					/>
					<Button type="submit" disabled={pending || direction.trim().length === 0}>
						{pending ? 'Sending…' : 'Send direction'}
					</Button>
				</form>
			)}
			{error && <p className="mt-2 text-xs text-red-600">{error}</p>}
		</div>
	)
}
