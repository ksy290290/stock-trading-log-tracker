import { useRouter } from 'expo-router';
import { useState } from 'react';
import { Alert } from 'react-native';

import { TradeForm } from '../../src/components/TradeForm';
import { notifyTradesChanged } from '../../src/refreshBus';
import { useApiClient } from '../../src/settings';
import { TradeInput } from '../../src/types';

export default function NewTradeScreen() {
  const router = useRouter();
  const api = useApiClient();
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (input: TradeInput) => {
    setSubmitting(true);
    try {
      await api.createTrade(input);
      notifyTradesChanged();
      router.back();
    } catch (e) {
      Alert.alert('저장 실패', e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  return <TradeForm submitLabel="추가" submitting={submitting} onSubmit={handleSubmit} />;
}
