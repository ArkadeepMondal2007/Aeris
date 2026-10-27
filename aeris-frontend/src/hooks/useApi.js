import { useCallback, useEffect, useState } from 'react'

export function useApi(fetcher, params, refreshKey = 0) {
  const paramsKey = JSON.stringify(params ?? {})
  const [retry, setRetry] = useState(0)
  const [state, setState] = useState({ data: null, error: null, loading: true })

  useEffect(() => {
    const controller = new AbortController()
    setState((previous) => ({ ...previous, loading: true, error: null }))
    fetcher(JSON.parse(paramsKey), controller.signal)
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((error) => {
        if (error.name !== 'AbortError') setState({ data: null, error: error.message, loading: false })
      })
    return () => controller.abort()
  }, [fetcher, paramsKey, refreshKey, retry])

  const refresh = useCallback(() => setRetry((count) => count + 1), [])
  return { ...state, refresh }
}
