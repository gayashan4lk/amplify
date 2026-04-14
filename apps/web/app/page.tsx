import { redirect } from 'next/navigation'

import { getServerSession } from '@/lib/auth-server'

export default async function Home() {
	const session = await getServerSession()
	redirect(session?.user?.id ? '/conversations' : '/login')
}
