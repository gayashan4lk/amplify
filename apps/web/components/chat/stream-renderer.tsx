// T049: renders the live streaming state — buffered text deltas and progress.

'use client'

import { useChatStore } from '@/lib/stores/chat-store'

export default function StreamRenderer() {
	const stream = useChatStore((s) => s.stream)
	const bufferedTexts = Object.entries(stream.textBufferByMessageId)

	if (!stream.activeAgent && !stream.progress && bufferedTexts.length === 0) {
		return null
	}

	return (
		<li className="self-stretch rounded-md border border-dashed px-4 py-3">
			{stream.activeAgent && (
				<div className="text-xs uppercase tracking-wide text-muted-foreground">
					{stream.activeAgent} working…
				</div>
			)}
			{stream.progress && (
				<div className="text-sm">
					<span className="font-medium">{stream.progress.phase}:</span>{' '}
					{stream.progress.message}
				</div>
			)}
			{bufferedTexts.map(([id, content]) => (
				<p key={id} className="mt-2 text-sm leading-6">
					{content}
				</p>
			))}
		</li>
	)
}
