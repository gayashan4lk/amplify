// T050: compact badge showing the currently active LangGraph node.

'use client'

import { useChatStore } from '@/lib/stores/chat-store'

const LABELS: Record<string, string> = {
	supervisor: 'Routing',
	research: 'Researching',
	clarification: 'Clarifying',
}

export default function AgentStatus() {
	const activeAgent = useChatStore((s) => s.stream.activeAgent)
	if (!activeAgent) return <div className="text-xs text-muted-foreground">Idle</div>
	return (
		<div className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs">
			<span className="h-2 w-2 animate-pulse rounded-full bg-blue-500" />
			{LABELS[activeAgent] ?? activeAgent}
		</div>
	)
}
