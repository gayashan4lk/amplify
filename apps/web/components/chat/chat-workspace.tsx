// Client-side container that mounts the chat store, the SSE client, and the
// three render components (message list + composer + status badge). Server
// components hand it the initial message list.

'use client'

import { useEffect } from 'react'

import AgentStatus from '@/components/chat/agent-status'
import MessageInput from '@/components/chat/message-input'
import MessageList from '@/components/chat/message-list'
import { useChatStore, type StoredMessage } from '@/lib/stores/chat-store'

type Props = {
	conversationId: string | null
	initialMessages: StoredMessage[]
}

export default function ChatWorkspace({ conversationId, initialMessages }: Props) {
	const loadInitial = useChatStore((s) => s.loadInitial)

	useEffect(() => {
		loadInitial(initialMessages, conversationId)
	}, [initialMessages, conversationId, loadInitial])

	return (
		<div className="flex h-full flex-col">
			<div className="flex items-center gap-3 border-b px-6 py-2">
				<AgentStatus />
			</div>
			<div className="flex-1 overflow-y-auto px-6 py-4">
				<MessageList />
			</div>
			<div className="border-t px-6 py-4">
				<MessageInput />
			</div>
		</div>
	)
}
