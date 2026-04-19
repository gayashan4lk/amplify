// ContentVariantGrid ephemeral component (T038, T048).
//
// Composes two <VariantCard /> side-by-side with a diversity-warning banner
// when the two variants turned out too similar even after one retry. Also
// propagates per-variant regeneration caps + the onRegenerate callback so
// each card can render its own regenerate affordance.

'use client'

import VariantCard from '@/components/ephemeral/variant-card'
import type {
	PostVariant,
	VariantLabel,
} from '@/lib/schemas/content'

type ProgressByLabel = Partial<
	Record<VariantLabel, { step: string; progress_hint?: number | null }>
>

type RegenerateHandler = (args: {
	label: VariantLabel
	additionalGuidance: string
}) => void | Promise<void>

type RetryHalfHandler = (args: {
	label: VariantLabel
	target: 'description' | 'image'
}) => void | Promise<void>

type Props = {
	requestId: string
	variants: PostVariant[]
	diversityWarning: boolean
	progress?: ProgressByLabel
	regenerationCaps?: Partial<Record<VariantLabel, number>>
	onRegenerate?: RegenerateHandler
	regeneratingLabel?: VariantLabel | null
	onRetryHalf?: RetryHalfHandler
	retryingByLabel?: Partial<Record<VariantLabel, 'description' | 'image' | null>>
}

export default function ContentVariantGrid({
	requestId,
	variants,
	diversityWarning,
	progress = {},
	regenerationCaps,
	onRegenerate,
	regeneratingLabel,
	onRetryHalf,
	retryingByLabel,
}: Props) {
	const byLabel = new Map<VariantLabel, PostVariant>()
	for (const v of variants) byLabel.set(v.label, v)

	const capFor = (label: VariantLabel): number | undefined => {
		if (regenerationCaps && typeof regenerationCaps[label] === 'number') {
			return regenerationCaps[label]
		}
		const v = byLabel.get(label)
		return v ? Math.max(0, 3 - v.regenerations_used) : undefined
	}

	return (
		<div
			className="flex flex-col gap-3"
			data-request-id={requestId}
			data-testid="content-variant-grid"
		>
			{diversityWarning && (
				<div className="rounded-md border border-yellow-300 bg-yellow-50 px-3 py-2 text-xs text-yellow-900">
					Heads up — both variants came out pretty similar. Try regenerating B
					or give different creative direction for more contrast.
				</div>
			)}
			<div className="grid grid-cols-1 gap-3 md:grid-cols-2">
				{(['A', 'B'] as const).map((l) => (
					<VariantCard
						key={l}
						label={l}
						variant={byLabel.get(l)}
						progress={progress[l] ?? null}
						remainingRegens={capFor(l)}
						onRegenerate={onRegenerate}
						regenerating={regeneratingLabel === l}
						onRetryHalf={onRetryHalf}
						retryingHalf={retryingByLabel?.[l] ?? null}
					/>
				))}
			</div>
		</div>
	)
}
