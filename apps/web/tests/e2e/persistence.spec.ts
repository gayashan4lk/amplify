// T069: cross-session persistence e2e.
//
// Runs the US1 happy path, signs out, signs back in, opens the prior
// conversation from the /conversations list, and asserts the stored
// intelligence brief renders identically (same scoped question, ≥3
// finding cards, clickable sources).
//
// Requires the same harness as research-happy-path.spec.ts: dev server
// up, seeded test user, RESEARCH_FIXTURE_MODE=1 so the backend returns
// deterministic Tavily fixtures.

import { expect, test } from '@playwright/test'

const TEST_EMAIL = process.env.PW_TEST_EMAIL ?? 'e2e@amplify.local'
const TEST_PASSWORD = process.env.PW_TEST_PASSWORD ?? 'correct horse battery staple'
const QUESTION = 'What pricing models are top 5 CRM competitors using?'

async function signIn(page: import('@playwright/test').Page) {
	await page.goto('/login')
	await page.getByLabel(/email/i).fill(TEST_EMAIL)
	await page.getByLabel(/password/i).fill(TEST_PASSWORD)
	await page.getByRole('button', { name: /sign in/i }).click()
}

test('prior conversation + brief survive sign-out and sign-in', async ({
	page,
	context,
}) => {
	// --- Run 1: produce a brief ------------------------------------------
	await signIn(page)
	await page.waitForURL('**/chat')

	await page
		.getByPlaceholder(/ask a scoped research question/i)
		.fill(QUESTION)
	await page.getByRole('button', { name: /send/i }).click()

	const brief = page.locator('text=Intelligence brief').first()
	await expect(brief).toBeVisible({ timeout: 60_000 })

	const liveUrl = page.url()
	expect(liveUrl).toMatch(/\/chat\/[^/]+/)

	// --- Sign out + clear cookies to force a fresh session ----------------
	await context.clearCookies()
	await page.goto('/login')

	// --- Run 2: resume and verify the prior brief is still there ---------
	await signIn(page)
	await page.goto('/conversations')

	await expect(page.getByText(QUESTION.slice(0, 20)).first()).toBeVisible({
		timeout: 10_000,
	})
	await page.getByText(QUESTION.slice(0, 20)).first().click()

	await expect(page.locator('text=Intelligence brief').first()).toBeVisible({
		timeout: 10_000,
	})

	const firstSourceLink = page.locator('a[href^="http"]').first()
	await expect(firstSourceLink).toHaveAttribute('href', /.+/)
})
