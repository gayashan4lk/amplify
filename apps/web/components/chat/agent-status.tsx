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
	if (!activeAgent) return (
		<div className="inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-bold text-slate-500">
			<span className="h-2 w-2 rounded-full bg-slate-500" />
			Idle
		</div>
	)
	

	return (
		<div className="inline-flex items-center gap-2 rounded-full border font-bold px-3 py-1 text-sm">
			<span className="h-2 w-2 animate-pulse rounded-full bg-blue-500 " />
			{LABELS[activeAgent] ?? activeAgent}
		</div>
	)
}
