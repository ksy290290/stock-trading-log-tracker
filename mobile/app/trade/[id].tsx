import { useLocalSearchParams, useRouter } from 'expo-router';
import { useEffect, useState } from 'react';
import { ActivityIndicator, Alert, StyleSheet, Text, View } from 'react-native';

import { TradeForm } from '../../src/components/TradeForm';
import { notifyTradesChanged } from '../../src/refreshBus';
import { useApiClient } from '../../src/settings';
import { Trade, TradeInput } from '../../src/types';

export default function EditTradeScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const tradeId = Number(id);
  const router = useRouter();
  const api = useApiClient();

  const [trade, setTrade] = useState<Trade | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try {
        const found = await api.getTrade(tradeId);
        setTrade(found);
      } catch (e) {
        setError(e instanceof Error ? e.message : String(e));
      } finally {
        setLoading(false);
      }
    })();
  }, [api, tradeId]);

  const handleSubmit = async (input: TradeInput) => {
    setSubmitting(true);
    try {
      await api.updateTrade(tradeId, input);
      notifyTradesChanged();
      router.back();
    } catch (e) {
      Alert.alert('저장 실패', e instanceof Error ? e.message : String(e));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = () => {
    Alert.alert('기록 삭제', '이 매매 기록을 삭제할까요?', [
      { text: '취소', style: 'cancel' },
      {
        text: '삭제',
        style: 'destructive',
        onPress: async () => {
          setSubmitting(true);
          try {
            await api.deleteTrade(tradeId);
            notifyTradesChanged();
            router.back();
          } catch (e) {
            Alert.alert('삭제 실패', e instanceof Error ? e.message : String(e));
            setSubmitting(false);
          }
        },
      },
    ]);
  };

  if (loading) {
    return (
      <View style={styles.centered}>
        <ActivityIndicator />
      </View>
    );
  }

  if (error || !trade) {
    return (
      <View style={styles.centered}>
        <Text style={styles.errorText}>{error ?? '기록을 찾을 수 없습니다.'}</Text>
      </View>
    );
  }

  return (
    <TradeForm
      initial={trade}
      submitLabel="저장"
      submitting={submitting}
      onSubmit={handleSubmit}
      onDelete={handleDelete}
    />
  );
}

const styles = StyleSheet.create({
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24 },
  errorText: { color: '#b91c1c', fontSize: 14 },
});
