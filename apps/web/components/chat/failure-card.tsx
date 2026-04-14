// T076 (Phase 5) also uses this. Imported from message-list so failures render
// in Phase 3 streams too — the full Retry wiring arrives in Phase 5.

'use client'

type Props = {
	code: string
	message: string
	recoverable: boolean
	suggestedAction?: string | null
}

export default function FailureCard({ code, message, recoverable, suggestedAction }: Props) {
	return (
		<div className="rounded-md border border-red-300 bg-red-50 p-4 text-sm">
			<div className="text-xs font-semibold uppercase tracking-wide text-red-700">
				{code}
			</div>
			<p className="mt-1 text-red-900">{message}</p>
			{suggestedAction && (
				<p className="mt-2 text-xs text-red-800">{suggestedAction}</p>
			)}
			{recoverable && (
				<div className="mt-2 text-xs text-red-700">Recoverable — retry available.</div>
			)}
		</div>
	)
}
