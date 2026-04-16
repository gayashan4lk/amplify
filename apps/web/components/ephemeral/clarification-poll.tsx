// T052: single-click clarification poll. On click, posts to
// /api/v1/chat/ephemeral via a proxy route and optimistically disables the
// poll. The same SSE stream that emitted the poll is still open and will
// receive the resumed research events.

'use client'

import { useState } from 'react'

import { Button } from '@/components/ui/button'

type Props = {
	messageId: string
	researchRequestId: string
	prompt: string
	options: string[]
	answered: boolean
}

export default function ClarificationPoll(props: Props) {
	const [answered, setAnswered] = useState(props.answered)
	const [selected, setSelected] = useState<number | null>(null)
	const [error, setError] = useState<string | null>(null)

	async function submit(index: number) {
		if (answered) return
		setSelected(index)
		setAnswered(true)
		try {
			const resp = await fetch('/api/chat/ephemeral', {
				method: 'POST',
				headers: { 'Content-Type': 'application/json' },
				body: JSON.stringify({
					research_request_id: props.researchRequestId,
					component_type: 'clarification_poll',
					response: { selected_option_index: index },
				}),
			})
			if (!resp.ok) throw new Error(await resp.text())
		} catch (e) {
			setAnswered(false)
			setSelected(null)
			setError(e instanceof Error ? e.message : 'failed to submit')
		}
	}

	return (
		<div className="rounded-md border bg-card p-4">
			<p className="mb-3 text-sm font-medium">{props.prompt}</p>
			<div className="flex flex-col gap-2">
				{props.options.map((opt, i) => (
					<Button
						key={opt}
						type="button"
						variant={selected === i ? 'default' : 'outline'}
						disabled={answered}
						onClick={() => submit(i)}
					>
						{opt}
					</Button>
				))}
			</div>
			{error && <p className="mt-2 text-xs text-red-700">{error}</p>}
		</div>
	)
}
