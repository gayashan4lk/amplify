import { redirect } from 'next/navigation'

import { getServerSession } from '@/lib/auth-server'
import { AuthForm } from '@/components/auth/auth-form'

export default async function SignupPage() {
	const session = await getServerSession()
	if (session?.user?.id) redirect('/chat')
	return <AuthForm mode="signup" />
}
