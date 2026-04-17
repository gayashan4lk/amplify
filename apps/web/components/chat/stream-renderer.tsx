// T049: renders the live streaming state — buffered text deltas and activity log.

'use client'

import { useChatStore } from '@/lib/stores/chat-store'

export default function StreamRenderer() {
	const stream = useChatStore((s) => s.stream)
	const bufferedTexts = Object.entries(stream.textBufferByMessageId)

	if (
		!stream.activeAgent &&
		!stream.progress &&
		bufferedTexts.length === 0 &&
		stream.activityEntries.length === 0
	) {
		return null
	}

	return (
		<li className="self-stretch rounded-md border border-dashed px-4 py-3">
			{stream.activeAgent && (
				<div className="text-xs uppercase tracking-wide text-muted-foreground">
					{stream.activeAgent} working…
				</div>
			)}
			{stream.activityEntries.length > 0 && (
				<ul className="mt-2 space-y-1 text-sm text-muted-foreground">
					{stream.activityEntries.map((e, i) => (
						<li key={i}>
							{e.kind === 'agent_start' && <>{e.agent} started</>}
							{e.kind === 'agent_end' && <>{e.agent} finished</>}
							{e.kind === 'progress' && (
								<>
									<span className="font-medium">{e.phase}:</span> {e.message}
								</>
							)}
						</li>
					))}
				</ul>
			)}
			{bufferedTexts.map(([id, content]) => (
				<p key={id} className="mt-2 text-sm leading-6">
					{content}
				</p>
			))}
		</li>
	)
}
