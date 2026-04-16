// T085: dev-only "view trace" link. Renders nothing in production or when
// no trace id is available. Points at LangSmith by default; override with
// NEXT_PUBLIC_TRACE_URL_TEMPLATE (must contain `{id}`).

'use client'

type Props = {
	traceId?: string | null
	className?: string
}

const DEFAULT_TEMPLATE = 'https://smith.langchain.com/trace/{id}'

export function TraceLink({ traceId, className }: Props) {
	if (process.env.NODE_ENV === 'production') return null
	if (!traceId) return null
	const template = process.env.NEXT_PUBLIC_TRACE_URL_TEMPLATE || DEFAULT_TEMPLATE
	const href = template.replace('{id}', encodeURIComponent(traceId))
	return (
		<a
			href={href}
			target="_blank"
			rel="noreferrer"
			className={`text-[10px] text-muted-foreground underline ${className ?? ''}`}
			data-testid="trace-link"
		>
			view trace
		</a>
	)
}
