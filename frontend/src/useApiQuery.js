import { useEffect, useState } from 'react';
import { api } from './api';

// 재조회와 화면 이동 시 이전 요청 취소를 공통으로 처리합니다.
export function useApiQuery(path, refreshKey) {
  const [revision, setRevision] = useState(0);
  const [state, setState] = useState({ path: null, data: null, error: '', loading: false });
  useEffect(() => {
    if (!path) return;
    const controller = new AbortController();
    setState((previous) => ({
      path,
      data: previous.path === path ? previous.data : null,
      error: '',
      loading: true,
    }));
    api(path, undefined, { signal: controller.signal })
      .then((data) => {
        if (!controller.signal.aborted) setState({ path, data, error: '', loading: false });
      })
      .catch((error) => {
        if (!controller.signal.aborted)
          setState((previous) => ({ ...previous, error: error.message, loading: false }));
      });
    return () => controller.abort();
  }, [path, revision, refreshKey]);
  const current = path && state.path === path ? state : { data: null, error: '', loading: !!path };
  return { ...current, reload: () => setRevision((value) => value + 1) };
}
