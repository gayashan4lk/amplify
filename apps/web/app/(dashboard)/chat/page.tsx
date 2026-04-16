// T044: the "new conversation" entry point. A fresh chat view with no
// hydrated history. When the user sends their first message the backend
// creates a Conversation and emits its id in the first SSE event.

import ChatWorkspace from '@/components/chat/chat-workspace'

export default function NewChatPage() {
	return <ChatWorkspace conversationId={null} initialMessages={[]} />
}
