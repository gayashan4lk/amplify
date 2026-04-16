import { headers } from 'next/headers'
import { auth } from './auth'

export async function getServerSession() {
	return auth.api.getSession({ headers: await headers() })
}

export async function requireUserId(): Promise<string> {
	const session = await getServerSession()
	if (!session?.user?.id) {
		throw new Error('unauthenticated')
	}
	return session.user.id
}
