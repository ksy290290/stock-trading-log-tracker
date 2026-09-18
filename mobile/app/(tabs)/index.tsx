import { Link, useRouter } from 'expo-router';
import { useCallback, useEffect, useState } from 'react';
import {
  FlatList,
  RefreshControl,
  StyleSheet,
  Text,
  TouchableOpacity,
  View,
} from 'react-native';

import { formatNumber } from '../../src/format';
import { useTradesVersion } from '../../src/refreshBus';
import { useApiClient, useSettings } from '../../src/settings';
import { Trade } from '../../src/types';

export default function TradesScreen() {
  const router = useRouter();
  const { baseUrl, loaded } = useSettings();
  const api = useApiClient();
  const version = useTradesVersion();

  const [trades, setTrades] = useState<Trade[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!baseUrl) {
      setTrades([]);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const data = await api.listTrades();
      setTrades(data);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, [api, baseUrl]);

  useEffect(() => {
    if (loaded) load();
  }, [loaded, version, load]);

  if (loaded && !baseUrl) {
    return (
      <View style={styles.centered}>
        <Text style={styles.emptyTitle}>API 서버가 설정되지 않았습니다</Text>
        <Text style={styles.emptyBody}>설정 탭에서 API 서버 주소를 먼저 입력해주세요.</Text>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      {error && (
        <View style={styles.errorBanner}>
          <Text style={styles.errorText}>{error}</Text>
        </View>
      )}
      <FlatList
        data={trades}
        keyExtractor={(item) => String(item.id)}
        refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
        contentContainerStyle={trades.length === 0 ? styles.emptyContainer : undefined}
        ListEmptyComponent={
          !loading ? (
            <View style={styles.centered}>
              <Text style={styles.emptyTitle}>아직 기록이 없습니다</Text>
              <Text style={styles.emptyBody}>오른쪽 아래 + 버튼으로 첫 매매를 기록해보세요.</Text>
            </View>
          ) : null
        }
        renderItem={({ item }) => (
          <TouchableOpacity
            style={styles.row}
            onPress={() => router.push(`/trade/${item.id}`)}
          >
            <View style={styles.rowHeader}>
              <Text style={styles.ticker}>
                {item.name ? `${item.name} (${item.ticker})` : item.ticker}
              </Text>
              <Text style={[styles.side, item.side === 'BUY' ? styles.buy : styles.sell]}>
                {item.side === 'BUY' ? '매수' : '매도'}
              </Text>
            </View>
            <Text style={styles.detail}>
              {item.trade_date} · {formatNumber(item.quantity, 2)}주 · {formatNumber(item.price)}
              {item.market === 'US' ? '$' : '원'}
            </Text>
            {item.strategy_tag && <Text style={styles.tag}>#{item.strategy_tag}</Text>}
          </TouchableOpacity>
        )}
      />
      <Link href="/trade/new" asChild>
        <TouchableOpacity style={styles.fab}>
          <Text style={styles.fabLabel}>+</Text>
        </TouchableOpacity>
      </Link>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  emptyContainer: { flexGrow: 1 },
  emptyTitle: { fontSize: 16, fontWeight: '600', color: '#374151', marginBottom: 6 },
  emptyBody: { fontSize: 14, color: '#6b7280', textAlign: 'center' },
  errorBanner: { backgroundColor: '#fee2e2', padding: 10 },
  errorText: { color: '#b91c1c', fontSize: 13 },
  row: {
    backgroundColor: '#fff',
    paddingHorizontal: 16,
    paddingVertical: 14,
    borderBottomWidth: StyleSheet.hairlineWidth,
    borderBottomColor: '#e5e7eb',
  },
  rowHeader: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center' },
  ticker: { fontSize: 16, fontWeight: '600', color: '#111827' },
  side: { fontSize: 13, fontWeight: '700', paddingHorizontal: 8, paddingVertical: 2, borderRadius: 6, overflow: 'hidden' },
  buy: { color: '#b91c1c', backgroundColor: '#fee2e2' },
  sell: { color: '#1d4ed8', backgroundColor: '#dbeafe' },
  detail: { fontSize: 13, color: '#6b7280', marginTop: 4 },
  tag: { fontSize: 12, color: '#9333ea', marginTop: 4 },
  fab: {
    position: 'absolute',
    right: 20,
    bottom: 24,
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: '#2563eb',
    alignItems: 'center',
    justifyContent: 'center',
    shadowColor: '#000',
    shadowOpacity: 0.2,
    shadowRadius: 6,
    shadowOffset: { width: 0, height: 3 },
    elevation: 4,
  },
  fabLabel: { color: '#fff', fontSize: 28, lineHeight: 30, marginTop: -2 },
});
