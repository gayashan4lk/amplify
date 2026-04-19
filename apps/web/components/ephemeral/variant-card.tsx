// VariantCard ephemeral component (T037).
//
// Renders one Facebook post variant: a 1:1 image, the description copy, and
// per-half status badges (description + image). If only one half is ready,
// the other renders a placeholder tile/spinner. Regenerate affordances are
// added later in T047 — this card only displays.

'use client'

import type { HalfStatus, PostVariant, VariantLabel } from '@/lib/schemas/content'

type Props = {
	variant?: PostVariant
	label: VariantLabel
	progress?: { step: string; progress_hint?: number | null } | null
}

const statusClass: Record<HalfStatus, string> = {
	ready: 'bg-green-100 text-green-800',
	pending: 'bg-yellow-100 text-yellow-800',
	failed: 'bg-red-100 text-red-800',
}

export default function VariantCard({ variant, label, progress }: Props) {
	const description = variant?.description ?? ''
	const descriptionStatus: HalfStatus = variant?.description_status ?? 'pending'
	const imageStatus: HalfStatus = variant?.image_status ?? 'pending'
	const imageUrl = variant?.image_signed_url ?? null

	return (
		<div
			className="flex flex-col rounded-lg border bg-card shadow-sm"
			data-testid={`variant-card-${label}`}
			data-variant-label={label}
		>
			<div className="flex items-center justify-between border-b px-4 py-2">
				<div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
					Variant {label}
				</div>
				<div className="flex gap-1">
					<span className={`rounded-full px-2 py-0.5 text-xs ${statusClass[descriptionStatus]}`}>
						copy {descriptionStatus}
					</span>
					<span className={`rounded-full px-2 py-0.5 text-xs ${statusClass[imageStatus]}`}>
						image {imageStatus}
					</span>
				</div>
			</div>

			<div className="relative aspect-square w-full overflow-hidden bg-muted">
				{imageUrl && imageStatus === 'ready' ? (
					// eslint-disable-next-line @next/next/no-img-element
					<img
						src={imageUrl}
						alt={`Variant ${label} visual`}
						className="h-full w-full object-cover"
						width={1080}
						height={1080}
					/>
				) : (
					<div className="flex h-full w-full items-center justify-center text-xs text-muted-foreground">
						{imageStatus === 'failed' ? 'Image failed' : 'Generating image…'}
					</div>
				)}
			</div>

			<div className="flex flex-1 flex-col gap-2 p-4">
				{description ? (
					<p className="whitespace-pre-wrap text-sm leading-6">{description}</p>
				) : (
					<p className="text-xs text-muted-foreground">
						{descriptionStatus === 'failed' ? 'Copy failed' : 'Drafting copy…'}
					</p>
				)}
				{progress && (
					<p className="text-xs text-muted-foreground">
						<span className="font-medium">{progress.step}</span>
						{typeof progress.progress_hint === 'number' && (
							<> · {Math.round(progress.progress_hint * 100)}%</>
						)}
					</p>
				)}
			</div>
		</div>
	)
}
