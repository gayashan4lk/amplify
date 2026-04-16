// T018: SSE type generator.
//
// For now this script acts as a contract-drift guard rather than a full code
// generator: the hand-maintained Zod module at lib/types/sse-events.ts is the
// source of truth on the frontend. This script checks that every documented
// event type from contracts/sse-events.md is represented in the Zod module.
//
// When this repo adopts `datamodel-code-generator` or a Pydantic→Zod emitter,
// replace the body of this file with the real generation step; the prebuild
// script entry point stays the same.

import { readFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const zodFile = resolve(here, '../lib/types/sse-events.ts')
const source = readFileSync(zodFile, 'utf8')

const REQUIRED_EVENT_TYPES = [
	'conversation_ready',
	'agent_start',
	'agent_end',
	'tool_call',
	'tool_result',
	'progress',
	'text_delta',
	'ephemeral_ui',
	'error',
	'done',
] as const

const missing = REQUIRED_EVENT_TYPES.filter((t) => !source.includes(`z.literal('${t}')`))
if (missing.length > 0) {
	console.error(`SSE type drift: missing z.literal('<type>') for: ${missing.join(', ')}`)
	process.exit(1)
}

console.log(`SSE Zod schemas cover all ${REQUIRED_EVENT_TYPES.length} documented event types.`)
