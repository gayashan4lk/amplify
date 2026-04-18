'use server'

import { auth } from '@/lib/auth'
import { revalidatePath } from 'next/cache'
import { headers } from 'next/headers'
import { redirect } from 'next/navigation'

export async function signOut() {
	try {
		await auth.api.signOut({
			headers: await headers(),
		})
	} catch (error) {
		console.error('User logout failed', error)
		return {
			success: false,
			message: 'Failed to logout',
		}
	}

	revalidatePath('/')
	redirect('/signin')
}
