// Typed client for the FastAPI backend (mirrors checkout/schemas.py).

export interface Item {
  id: number
  name: string
  description: string | null
  created_at: string
}

export interface ItemCreate {
  name: string
  description: string | null
}

/** Field name -> error message, built from FastAPI's 422 response. */
export type FieldErrors = Partial<Record<keyof ItemCreate, string>>

export class ValidationFailed extends Error {
  readonly fieldErrors: FieldErrors

  constructor(fieldErrors: FieldErrors) {
    super('Validation failed')
    this.fieldErrors = fieldErrors
  }
}

// FastAPI's validation error format: {"detail": [{"loc": ["body", "name"], "msg": "..."}]}
interface FastApiValidationError {
  detail: { loc: (string | number)[]; msg: string }[]
}

const API = '/api'

export async function listItems(): Promise<Item[]> {
  const res = await fetch(`${API}/items`)
  if (!res.ok) throw new Error(`Loading items failed (HTTP ${res.status})`)
  return res.json()
}

export async function createItem(data: ItemCreate): Promise<Item> {
  const res = await fetch(`${API}/items`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  })
  if (res.status === 422) {
    const body = (await res.json()) as FastApiValidationError
    const errors: FieldErrors = {}
    for (const err of body.detail) {
      const field = err.loc.at(-1)
      if (field === 'name' || field === 'description') errors[field] = err.msg
    }
    throw new ValidationFailed(errors)
  }
  if (!res.ok) throw new Error(`Saving failed (HTTP ${res.status})`)
  return res.json()
}
