// T084: FailureCard renders from an injected SSE error event and the Retry
// button re-submits the original user message.
//
// We intercept the /api/chat/stream proxy route and reply with a
// hand-crafted SSE error frame so the test is deterministic and hermetic.

import { expect, test } from '@playwright/test'

const ERROR_FRAME = [
	'id: 1',
	'event: error',
	JSON.stringify({
		v: 1,
		type: 'error',
		conversation_id: 'c_test',
		at: new Date().toISOString(),
		code: 'tavily_unavailable',
		message: 'Our search provider is temporarily unreachable.',
		recoverable: true,
		suggested_action: 'Try again in a minute.',
		failure_record_id: 'fr_test',
	}),
	'',
	'',
].join('\n')

test('failure card renders and retry re-submits the last user message', async ({ page }) => {
	let hits = 0
	await page.route('**/api/chat/stream*', async (route) => {
		hits += 1
		await route.fulfill({
			status: 200,
			headers: { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache' },
			body: ERROR_FRAME,
		})
	})

	await page.goto('/chat')
	const textarea = page.getByPlaceholder('Ask a scoped research question…')
	await textarea.fill('What pricing models do top CRMs use?')
	await page.getByRole('button', { name: 'Send' }).click()

	await expect(page.getByText('Our search provider is temporarily unreachable.')).toBeVisible()

	const retry = page.getByTestId('failure-retry')
	await expect(retry).toBeVisible()
	await retry.click()

	await expect.poll(() => hits).toBeGreaterThanOrEqual(2)
})
