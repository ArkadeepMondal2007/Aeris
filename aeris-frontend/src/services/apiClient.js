const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000').replace(/\/$/, '')

export class ApiError extends Error {}

export async function getJson(path, { params, signal } = {}) {
  const url = new URL(BASE_URL + path)
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') url.searchParams.set(key, value)
  })

  let response
  try {
    response = await fetch(url, { signal, headers: { Accept: 'application/json' } })
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError(`Cannot reach the API at ${BASE_URL}. Check that the backend is running.`)
  }
  if (!response.ok) throw new ApiError(`The API responded with status ${response.status}.`)
  try {
    return await response.json()
  } catch {
    throw new ApiError('The API returned a response that is not valid JSON.')
  }
}
