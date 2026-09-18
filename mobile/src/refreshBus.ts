import { useSyncExternalStore } from 'react';

// 매매 기록이 추가/수정/삭제된 뒤 목록/분석 화면이 다시 불러오도록 하는 최소한의
// 알림 장치. expo-router 탭은 화면 전환 시 언마운트되지 않아서 그냥 useEffect만으론
// "추가 화면 -> 뒤로가기" 후 목록이 갱신되지 않음.
type Listener = () => void;

const listeners = new Set<Listener>();
let version = 0;

export function notifyTradesChanged() {
  version += 1;
  listeners.forEach((listener) => listener());
}

export function useTradesVersion() {
  return useSyncExternalStore(
    (onStoreChange) => {
      listeners.add(onStoreChange);
      return () => listeners.delete(onStoreChange);
    },
    () => version
  );
}
