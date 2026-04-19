// VariantCard ephemeral component (T037, T047).
//
// Renders one Facebook post variant: a 1:1 image, the description copy, and
// per-half status badges (description + image). When `onRegenerate` is
// provided, also renders a regenerate affordance (button + optional guidance
// textbox) that is disabled once `remainingRegens` hits 0.

'use client'

import { useState } from 'react'

import type { HalfStatus, PostVariant, VariantLabel } from '@/lib/schemas/content'

type Props = {
	variant?: PostVariant
	label: VariantLabel
	progress?: { step: string; progress_hint?: number | null } | null
	remainingRegens?: number
	onRegenerate?: (args: { label: VariantLabel; additionalGuidance: string }) => void | Promise<void>
	regenerating?: boolean
}

const statusClass: Record<HalfStatus, string> = {
	ready: 'bg-green-100 text-green-800',
	pending: 'bg-yellow-100 text-yellow-800',
	failed: 'bg-red-100 text-red-800',
}

export default function VariantCard({
	variant,
	label,
	progress,
	remainingRegens,
	onRegenerate,
	regenerating,
}: Props) {
	const description = variant?.description ?? ''
	const descriptionStatus: HalfStatus = variant?.description_status ?? 'pending'
	const imageStatus: HalfStatus = variant?.image_status ?? 'pending'
	const imageUrl = variant?.image_signed_url ?? null

	const [showGuidance, setShowGuidance] = useState(false)
	const [guidance, setGuidance] = useState('')

	const capKnown = typeof remainingRegens === 'number'
	const disabledRegen =
		!onRegenerate ||
		regenerating === true ||
		(capKnown && remainingRegens! <= 0) ||
		descriptionStatus !== 'ready' ||
		imageStatus !== 'ready'

	const regenLabel = (() => {
		if (regenerating) return 'Regenerating…'
		if (capKnown && remainingRegens! <= 0) return 'No regenerations left'
		if (capKnown) return `Regenerate (${remainingRegens} left)`
		return 'Regenerate'
	})()

	async function handleSubmit() {
		if (!onRegenerate || disabledRegen) return
		await onRegenerate({ label, additionalGuidance: guidance.trim() })
		setGuidance('')
		setShowGuidance(false)
	}

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
				{onRegenerate && (
					<div className="mt-auto flex flex-col gap-2 pt-2">
						{showGuidance && (
							<textarea
								value={guidance}
								onChange={(e) => setGuidance(e.target.value)}
								placeholder={`Optional guidance for variant ${label}…`}
								className="w-full rounded border p-2 text-xs"
								rows={2}
								maxLength={2000}
								data-testid={`regenerate-guidance-${label}`}
							/>
						)}
						<div className="flex items-center justify-between gap-2">
							<button
								type="button"
								onClick={() => setShowGuidance((v) => !v)}
								disabled={disabledRegen}
								className="text-xs text-muted-foreground underline-offset-2 hover:underline disabled:pointer-events-none disabled:opacity-40"
							>
								{showGuidance ? 'hide guidance' : 'add guidance'}
							</button>
							<button
								type="button"
								onClick={handleSubmit}
								disabled={disabledRegen}
								data-testid={`regenerate-${label}`}
								className="rounded-md border bg-background px-3 py-1 text-xs font-medium hover:bg-accent disabled:pointer-events-none disabled:opacity-40"
							>
								{regenLabel}
							</button>
						</div>
					</div>
				)}
			</div>
		</div>
	)
}
