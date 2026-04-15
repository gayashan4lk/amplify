// T076: renders an `error` SSE event / persisted FailureRecord as a distinct
// in-conversation card. When `recoverable` and an `onRetry` handler is
// supplied, a Retry button re-submits the original user message.

'use client'

import { Button } from '@/components/ui/button'

type Props = {
	code: string
	message: string
	recoverable: boolean
	suggestedAction?: string | null
	onRetry?: () => void
}

export default function FailureCard({
	code,
	message,
	recoverable,
	suggestedAction,
	onRetry,
}: Props) {
	return (
		<div className="rounded-md border border-red-300 bg-red-50 p-4 text-sm">
			<div className="text-xs font-semibold uppercase tracking-wide text-red-700">
				{code}
			</div>
			<p className="mt-1 text-red-900">{message}</p>
			{suggestedAction && (
				<p className="mt-2 text-xs text-red-800">{suggestedAction}</p>
			)}
			{recoverable && onRetry && (
				<div className="mt-3">
					<Button
						type="button"
						size="sm"
						variant="outline"
						onClick={onRetry}
						data-testid="failure-retry"
					>
						Retry
					</Button>
				</div>
			)}
		</div>
	)
}
