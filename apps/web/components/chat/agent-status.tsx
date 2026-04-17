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
		<div className="inline-flex items-center gap-2 rounded-md border border-dashed px-3 py-1 text-sm font-bold text-slate-500">
			<span className="h-3 w-3 rounded-md bg-slate-500" />
			Idle
		</div>
	)
	
	return (
		<div className="inline-flex items-center gap-2 rounded-md border border-dashed font-bold px-3 py-1 text-sm">
			<span className="h-3 w-3 animate-pulse rounded-md bg-blue-500 " />
			{LABELS[activeAgent] ?? activeAgent}
		</div>
	)
}
