export async function api<T>(url: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(url, options)
  const value = await response.json().catch(() => null)
  if (!response.ok) {
    const detail = value?.detail
    const message = typeof detail === 'string' ? detail
      : Array.isArray(detail) ? detail.map((item: { msg: string }) => item.msg).join(' ')
        : `No se pudo contactar con la API (HTTP ${response.status}).`
    throw new Error(message)
  }
  return value as T
}
