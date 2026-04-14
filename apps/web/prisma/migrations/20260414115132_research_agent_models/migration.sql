/*
  Warnings:

  - You are about to drop the `Post` table. If the table is not empty, all the data it contains will be lost.

*/
-- CreateEnum
CREATE TYPE "MessageRole" AS ENUM ('user', 'system', 'assistant');

-- CreateEnum
CREATE TYPE "ResearchStatus" AS ENUM ('pending', 'running', 'complete', 'failed', 'cancelled');

-- CreateEnum
CREATE TYPE "FailureCode" AS ENUM ('tavily_unavailable', 'tavily_rate_limited', 'llm_unavailable', 'llm_invalid_output', 'no_findings_above_threshold', 'user_cancelled', 'budget_exceeded', 'rate_limited_user');

-- DropTable
DROP TABLE "Post";

-- CreateTable
CREATE TABLE "conversation" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "title" TEXT NOT NULL,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,
    "archivedAt" TIMESTAMP(3),

    CONSTRAINT "conversation_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "message" (
    "id" TEXT NOT NULL,
    "conversationId" TEXT NOT NULL,
    "role" "MessageRole" NOT NULL,
    "content" TEXT NOT NULL,
    "briefId" TEXT,
    "progressEvents" JSONB NOT NULL DEFAULT '[]',
    "failureRecordId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "message_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "research_request" (
    "id" TEXT NOT NULL,
    "conversationId" TEXT NOT NULL,
    "messageId" TEXT NOT NULL,
    "rawQuestion" TEXT NOT NULL,
    "scopedQuestion" TEXT NOT NULL,
    "plan" JSONB,
    "status" "ResearchStatus" NOT NULL DEFAULT 'pending',
    "budgetQueries" INTEGER NOT NULL DEFAULT 8,
    "budgetSeconds" INTEGER NOT NULL DEFAULT 60,
    "startedAt" TIMESTAMP(3),
    "completedAt" TIMESTAMP(3),
    "briefId" TEXT,
    "failureRecordId" TEXT,

    CONSTRAINT "research_request_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "failure_record" (
    "id" TEXT NOT NULL,
    "code" "FailureCode" NOT NULL,
    "recoverable" BOOLEAN NOT NULL,
    "userMessage" TEXT NOT NULL,
    "suggestedAction" TEXT,
    "traceId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "failure_record_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "conversation_userId_updatedAt_idx" ON "conversation"("userId", "updatedAt" DESC);

-- CreateIndex
CREATE INDEX "message_conversationId_createdAt_idx" ON "message"("conversationId", "createdAt");

-- CreateIndex
CREATE INDEX "research_request_conversationId_startedAt_idx" ON "research_request"("conversationId", "startedAt");

-- AddForeignKey
ALTER TABLE "conversation" ADD CONSTRAINT "conversation_userId_fkey" FOREIGN KEY ("userId") REFERENCES "user"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "message" ADD CONSTRAINT "message_conversationId_fkey" FOREIGN KEY ("conversationId") REFERENCES "conversation"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "message" ADD CONSTRAINT "message_failureRecordId_fkey" FOREIGN KEY ("failureRecordId") REFERENCES "failure_record"("id") ON DELETE SET NULL ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "research_request" ADD CONSTRAINT "research_request_conversationId_fkey" FOREIGN KEY ("conversationId") REFERENCES "conversation"("id") ON DELETE CASCADE ON UPDATE CASCADE;
