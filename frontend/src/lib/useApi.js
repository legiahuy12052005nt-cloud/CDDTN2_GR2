import { useCallback, useEffect, useRef, useState } from 'react'
import { errorMessage } from '../api/client.js'

// Gọi API khi deps đổi; trả { data, error, loading, reload }. Bỏ kết quả cũ nếu có lời gọi mới hơn.
export default function useApi(fn, deps = [], { skip = false } = {}) {
  const [state, setState] = useState({ data: null, error: null, loading: !skip })
  const seq = useRef(0)
  const run = useCallback(() => {
    if (skip) return
    const id = ++seq.current
    setState((s) => ({ ...s, loading: true, error: null }))
    fn()
      .then((data) => id === seq.current && setState({ data, error: null, loading: false }))
      .catch((e) => id === seq.current && setState({ data: null, error: errorMessage(e), loading: false }))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, skip])
  useEffect(run, [run])
  return { ...state, reload: run }
}
