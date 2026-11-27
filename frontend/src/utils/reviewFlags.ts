/** Plain-language names for evaluation flags, and how much attention they need. */
export const flagText: Record<string, string> = {
  missing_answer: 'No answer found',
  unreadable_answer: 'Unreadable — mark it yourself',
  invalid_ai_output: 'AI output rejected — mark it yourself',
  evidence_not_found: 'Quoted evidence not found in the answer',
  incomplete: 'Some questions need your marks',
  verifier_disagrees: 'Verifier disagrees',
  verification_failed: 'Verification could not run',
  math_disagrees: 'SymPy check contradicts the marks',
  math_uncertain: 'SymPy could not read the answer',
  similarity_mismatch: 'Marks and content similarity disagree',
}

export function needsAttention(flags: string[]): boolean {
  return flags.some((flag) => flag !== 'missing_answer')
}

export const reviewStatusLabel = { pending: 'Awaiting review', approved: 'Approved', rejected: 'Sent back' } as const
export const verificationLabel = {
  pending: 'Not checked',
  completed: 'Verified',
  skipped: 'Local checks only',
  failed: 'Verification failed',
} as const
