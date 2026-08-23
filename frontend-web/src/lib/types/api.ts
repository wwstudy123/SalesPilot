export type ApiEnvelope<T> = {
  code: string
  message: string
  data: T
}

export type LoginResult = {
  token: string
  employeeId: number
  name: string
  role: string
}

export type Employee = {
  id: number
  username: string
  name: string
  role: string
  phone: string | null
}

export type Customer = {
  id: number
  ownerId: number
  name: string
  phone: string | null
  gender: string
  lifecycleStage: string
  source: string | null
  remark: string | null
  createdAt: string | null
  updatedAt: string | null
}

export type FollowUp = {
  id: number
  customerId: number
  employeeId: number
  channel: string
  content: string
  nextFollowAt: string | null
  createdAt: string | null
}

export type Purchase = {
  id: number
  customerId: number
  productName: string
  category: string
  amount: number
  quantity: number
  purchasedAt: string | null
  remark: string | null
  createdAt: string | null
}

// ---------- M4：画像与提案（HITL） ----------

export type ProfileField = {
  id: number
  customerId: number
  fieldKey: string
  fieldValue: string
  evidence: string | null
  version: number
  updatedBy: number | null
  updatedAt: string | null
}

export type ProposalField = {
  fieldKey: string
  fieldValue: string
  evidence: string
  oldValue?: string
}

export type Proposal = {
  id: string
  customer_id: number
  employee_id: number
  tool: string
  fields: ProposalField[]
  status: string
  run_id: string | null
  source: string | null
  created_at: string
  expires_at: string
  resolved_at: string | null
}

export type ProfileRefreshResult = {
  outcome: 'first_visit_checklist' | 'no_change' | 'proposal' | 'error'
  customer_id: number
  record_count?: number
  checklist?: string[]
  proposal?: Proposal
  merged?: boolean
  error?: string
  run_id: string
}

export type AwaitingConfirmation = {
  pauseAfterSection: number
  nextSection: number
  completedCount: number
  status?: string | null
}

export type Run = {
  runId: string
  projectId: string
  status: string
  kernelStatus: string
  phase: string | null
  flow: string | null
  provider: string | null
  model: string | null
  currentSection: number | null
  completedCount: number | null
  totalWordCount: number | null
  awaitingConfirmation?: AwaitingConfirmation | null
}

export type RunListResponse = {
  items: Run[]
}

export type RunEventsResponse = {
  run_id: string
  after_seq: number
  limit: number
  returned_count: number
  total_available: number
  next_after_seq: number
  has_more: boolean
  items: Array<Record<string, unknown>>
}

export type RunEventPayload = Record<string, unknown> & {
  summary?: string
  delta?: string
  level?: string
  event?: string
  awaiting_confirmation?: AwaitingConfirmation
}

export type RunEvent = {
  eventId: string
  seq: number
  type: string
  category: string
  time: string
  payload: RunEventPayload
}

export type RunEventStreamHandler = (event: RunEvent) => void

export type RunAck = {
  run_id: string
  status: string
  kernel_status?: string | null
  accepted?: boolean | null
}

export type ResumeRunRequest = {
  prompt?: string
}

export type RunInstructionRequest = {
  kind: string
  text?: string
}
