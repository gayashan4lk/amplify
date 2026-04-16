// T051: renders an IntelligenceBrief with:
// - header (scoped question + status)
// - ordered finding cards with claim, evidence, confidence badge, and an
//   expandable sources list
// - unsourced and contradiction indicators per intelligence-brief.md
//   invariants 2 and 5 and FR-017

'use client'

import { useState } from 'react'

import { TraceLink } from '@/components/dev/trace-link'
import type { IntelligenceBrief } from '@/lib/types/sse-events'

type Props = { brief: IntelligenceBrief }

const confidenceColor: Record<string, string> = {
	high: 'bg-green-100 text-green-800',
	medium: 'bg-yellow-100 text-yellow-800',
	low: 'bg-gray-100 text-gray-700',
}

const sourceIcon: Record<string, string> = {
	news: '📰',
	blog: '📝',
	forum: '💬',
	competitor_site: '🏢',
	official: '🏛️',
	ad_library: '📣',
	analytics: '📊',
	other: '🔗',
}

export default function IntelligenceBriefComponent({ brief }: Props) {
	return (
		<div className="rounded-lg border bg-card p-5 shadow-sm">
			<header className="mb-4 flex items-start justify-between gap-4">
				<div>
					<div className="text-xs uppercase tracking-wide text-muted-foreground">
						Intelligence brief
					</div>
					<h3 className="text-base font-semibold leading-tight">
						{brief.scoped_question}
					</h3>
				</div>
				<span
					className={`rounded-full px-2 py-0.5 text-xs font-medium ${
						brief.status === 'complete'
							? 'bg-green-100 text-green-800'
							: 'bg-yellow-100 text-yellow-800'
					}`}
				>
					{brief.status === 'complete' ? 'Complete' : 'Low confidence'}
				</span>
			</header>

			<ol className="flex flex-col gap-3">
				{brief.findings.map((f) => (
					<FindingCard key={f.id} finding={f} traceId={brief.trace_id ?? null} />
				))}
			</ol>
		</div>
	)
}

function FindingCard({
	finding,
	traceId,
}: {
	finding: IntelligenceBrief['findings'][number]
	traceId: string | null
}) {
	const [expanded, setExpanded] = useState(false)
	return (
		<li className="rounded-md border p-4">
			<div className="mb-1 flex items-center gap-2">
				<span className="text-xs font-semibold text-muted-foreground">
					#{finding.rank}
				</span>
				<span
					className={`rounded-full px-2 py-0.5 text-xs ${
						confidenceColor[finding.confidence] ?? 'bg-gray-100'
					}`}
				>
					{finding.confidence}
				</span>
				{finding.unsourced && (
					<span className="rounded-full bg-orange-100 px-2 py-0.5 text-xs text-orange-800">
						unsourced
					</span>
				)}
				{finding.contradicts && finding.contradicts.length > 0 && (
					<span className="rounded-full bg-red-100 px-2 py-0.5 text-xs text-red-800">
						contradicts {finding.contradicts.join(', ')}
					</span>
				)}
			</div>
			<p className="text-sm font-medium">{finding.claim}</p>
			<p className="mt-1 text-sm text-muted-foreground">{finding.evidence}</p>
			{finding.notes && (
				<p className="mt-2 text-xs italic text-muted-foreground">{finding.notes}</p>
			)}
			<div className="mt-2 flex items-center gap-3">
				<button
					type="button"
					className="text-xs text-blue-600 underline"
					onClick={() => setExpanded((e) => !e)}
				>
					{expanded
						? 'Hide sources'
						: `Show sources (${finding.sources.length})`}
				</button>
				<TraceLink traceId={traceId} />
			</div>
			{expanded && (
				<ul className="mt-2 flex flex-col gap-1 text-xs">
					{finding.sources.map((s) => (
						<li key={s.url} className="flex items-start gap-2">
							<span>{sourceIcon[s.source_type] ?? '🔗'}</span>
							<a
								className="text-blue-600 underline"
								href={s.url}
								target="_blank"
								rel="noreferrer"
							>
								{s.title}
							</a>
							{!s.accessible && (
								<span className="text-orange-700">(paywalled)</span>
							)}
						</li>
					))}
				</ul>
			)}
		</li>
	)
}
