// ContentVariantGrid ephemeral component (T038).
//
// Composes two <VariantCard /> side-by-side with a diversity-warning banner
// when the two variants turned out too similar even after one retry.

'use client'

import VariantCard from '@/components/ephemeral/variant-card'
import type {
	PostVariant,
	VariantLabel,
} from '@/lib/schemas/content'

type ProgressByLabel = Partial<
	Record<VariantLabel, { step: string; progress_hint?: number | null }>
>

type Props = {
	requestId: string
	variants: PostVariant[]
	diversityWarning: boolean
	progress?: ProgressByLabel
}

export default function ContentVariantGrid({
	requestId,
	variants,
	diversityWarning,
	progress = {},
}: Props) {
	const byLabel = new Map<VariantLabel, PostVariant>()
	for (const v of variants) byLabel.set(v.label, v)

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
				<VariantCard
					label="A"
					variant={byLabel.get('A')}
					progress={progress.A ?? null}
				/>
				<VariantCard
					label="B"
					variant={byLabel.get('B')}
					progress={progress.B ?? null}
				/>
			</div>
		</div>
	)
}
