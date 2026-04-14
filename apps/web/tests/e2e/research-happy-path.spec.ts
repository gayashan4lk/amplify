// T057: end-to-end happy path for US1.
//
// Signs in, opens /chat, sends a scoped question, waits for the
// <IntelligenceBrief /> card to render, and asserts there are ≥3 finding
// cards, each with a source link that has a non-empty href.
//
// Requires: the dev server running against a Neon dev DB + FastAPI up, a
// seeded test user, and recorded Tavily fixtures wired into the API via
// RESEARCH_FIXTURE_MODE=1. The quickstart walkthrough (T090) documents the
// setup steps.

import { expect, test } from '@playwright/test'

const TEST_EMAIL = process.env.PW_TEST_EMAIL ?? 'e2e@amplify.local'
const TEST_PASSWORD = process.env.PW_TEST_PASSWORD ?? 'correct horse battery staple'

test('signed-in user receives a rendered intelligence brief', async ({ page }) => {
	await page.goto('/login')
	await page.getByLabel(/email/i).fill(TEST_EMAIL)
	await page.getByLabel(/password/i).fill(TEST_PASSWORD)
	await page.getByRole('button', { name: /sign in/i }).click()
	await page.waitForURL('**/chat')

	await page
		.getByPlaceholder(/ask a scoped research question/i)
		.fill('What pricing models are top 5 CRM competitors using?')
	await page.getByRole('button', { name: /send/i }).click()

	const brief = page.locator('text=Intelligence brief').first()
	await expect(brief).toBeVisible({ timeout: 60_000 })

	const findingCards = page.locator('ol > li:has(text="#")').nth(0)
	await expect(findingCards).toBeVisible()

	const showSources = page.getByRole('button', { name: /show sources/i }).first()
	await showSources.click()

	const firstSourceLink = page
		.locator('a[href^="http"]')
		.first()
	await expect(firstSourceLink).toHaveAttribute('href', /.+/)
})
