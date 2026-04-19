// VariantCard ephemeral component (T037, T047, T051, T052).
//
// Renders one Facebook post variant: a 1:1 image, the description copy, and
// per-half status badges (description + image). When `onRegenerate` is
// provided, also renders a regenerate affordance (button + optional guidance
// textbox) that is disabled once `remainingRegens` hits 0.
//
// Also exposes copy-description and download-image actions whenever both
// halves are ready. The download path tolerates signed-URL expiry by
// refreshing through `GET /api/v1/content/image/{image_key}` on 403.

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
	onRetryHalf?: (args: { label: VariantLabel; target: 'description' | 'image' }) => void | Promise<void>
	retryingHalf?: 'description' | 'image' | null
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
	onRetryHalf,
	retryingHalf,
}: Props) {
	const description = variant?.description ?? ''
	const descriptionStatus: HalfStatus = variant?.description_status ?? 'pending'
	const imageStatus: HalfStatus = variant?.image_status ?? 'pending'
	const imageUrl = variant?.image_signed_url ?? null

	const [showGuidance, setShowGuidance] = useState(false)
	const [guidance, setGuidance] = useState('')
	const [copyState, setCopyState] = useState<'idle' | 'copied' | 'error'>('idle')
	const [downloading, setDownloading] = useState(false)

	const bothReady = descriptionStatus === 'ready' && imageStatus === 'ready'

	async function handleCopy() {
		if (!description) return
		try {
			await navigator.clipboard.writeText(description)
			setCopyState('copied')
			setTimeout(() => setCopyState('idle'), 1500)
		} catch {
			setCopyState('error')
			setTimeout(() => setCopyState('idle'), 1500)
		}
	}

	async function fetchImageBlob(url: string): Promise<Blob> {
		const resp = await fetch(url, { credentials: 'omit' })
		if (resp.status === 403 && variant?.image_key) {
			// Signed URL may have expired — refresh and retry once.
			const refreshed = await fetch(
				`/api/v1/content/image/${encodeURIComponent(variant.image_key)}`,
				{ credentials: 'include' },
			)
			if (!refreshed.ok) throw new Error('refresh_failed')
			const data = (await refreshed.json()) as { signed_url: string }
			const retry = await fetch(data.signed_url, { credentials: 'omit' })
			if (!retry.ok) throw new Error('download_failed')
			return await retry.blob()
		}
		if (!resp.ok) throw new Error('download_failed')
		return await resp.blob()
	}

	async function handleDownload() {
		if (!imageUrl || !bothReady || downloading) return
		setDownloading(true)
		try {
			const blob = await fetchImageBlob(imageUrl)
			const mime = blob.type || 'image/png'
			const ext = mime.includes('jpeg') || mime.includes('jpg') ? 'jpg' : 'png'
			const objectUrl = URL.createObjectURL(blob)
			const a = document.createElement('a')
			a.href = objectUrl
			a.download = `variant-${label}.${ext}`
			document.body.appendChild(a)
			a.click()
			a.remove()
			setTimeout(() => URL.revokeObjectURL(objectUrl), 1000)
		} catch {
			// Silent failure — user can retry.
		} finally {
			setDownloading(false)
		}
	}

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
				{(descriptionStatus === 'failed' || imageStatus === 'failed') && onRetryHalf && (
					<div className="flex items-center gap-2 pt-2">
						{descriptionStatus === 'failed' && (
							<button
								type="button"
								onClick={() => onRetryHalf({ label, target: 'description' })}
								disabled={retryingHalf === 'description'}
								data-testid={`retry-description-${label}`}
								className="rounded-md border border-red-200 bg-red-50 px-3 py-1 text-xs font-medium text-red-900 hover:bg-red-100 disabled:pointer-events-none disabled:opacity-40"
							>
								{retryingHalf === 'description' ? 'Retrying…' : 'Retry description'}
							</button>
						)}
						{imageStatus === 'failed' && (
							<button
								type="button"
								onClick={() => onRetryHalf({ label, target: 'image' })}
								disabled={retryingHalf === 'image'}
								data-testid={`retry-image-${label}`}
								className="rounded-md border border-red-200 bg-red-50 px-3 py-1 text-xs font-medium text-red-900 hover:bg-red-100 disabled:pointer-events-none disabled:opacity-40"
							>
								{retryingHalf === 'image' ? 'Retrying…' : 'Retry image'}
							</button>
						)}
					</div>
				)}
				{bothReady && (
					<div className="flex items-center gap-2 pt-2">
						<button
							type="button"
							onClick={handleCopy}
							data-testid={`copy-description-${label}`}
							className="rounded-md border bg-background px-3 py-1 text-xs font-medium hover:bg-accent"
						>
							{copyState === 'copied'
								? 'Copied ✓'
								: copyState === 'error'
									? 'Copy failed'
									: 'Copy description'}
						</button>
						<button
							type="button"
							onClick={handleDownload}
							disabled={downloading}
							data-testid={`download-image-${label}`}
							className="rounded-md border bg-background px-3 py-1 text-xs font-medium hover:bg-accent disabled:pointer-events-none disabled:opacity-40"
						>
							{downloading ? 'Downloading…' : 'Download image'}
						</button>
					</div>
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
