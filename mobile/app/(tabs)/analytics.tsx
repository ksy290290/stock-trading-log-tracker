import { useCallback, useEffect, useState } from 'react';
import { FlatList, RefreshControl, StyleSheet, Text, View } from 'react-native';

import { formatNumber, formatPercent, formatSigned } from '../../src/format';
import { useTradesVersion } from '../../src/refreshBus';
import { useApiClient, useSettings } from '../../src/settings';
import { Position, Summary } from '../../src/types';

export default function AnalyticsScreen() {
  const { baseUrl, loaded } = useSettings();
  const api = useApiClient();
  const version = useTradesVersion();

  const [summary, setSummary] = useState<Summary | null>(null);
  const [positions, setPositions] = useState<Position[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!baseUrl) return;
    setLoading(true);
    setError(null);
    try {
      const [summaryData, positionsData] = await Promise.all([api.getSummary(), api.getPositions()]);
      setSummary(summaryData);
      setPositions(positionsData.filter((p) => p.qty > 0));
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
    <FlatList
      style={styles.container}
      data={positions}
      keyExtractor={(item) => item.ticker}
      refreshControl={<RefreshControl refreshing={loading} onRefresh={load} />}
      ListHeaderComponent={
        <View>
          {error && (
            <View style={styles.errorBanner}>
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}
          {summary && (
            <View style={styles.summaryGrid}>
              <SummaryCard label="총 실현손익" value={`${formatSigned(summary.total_realized_pnl)}원`} positive={summary.total_realized_pnl >= 0} />
              <SummaryCard label="총 평가손익" value={`${formatSigned(summary.total_unrealized_pnl)}원`} positive={summary.total_unrealized_pnl >= 0} />
              <SummaryCard label="승률" value={formatPercent(summary.win_rate)} />
              <SummaryCard label="총 거래 건수" value={`${summary.trade_count}건`} />
            </View>
          )}
          <Text style={styles.sectionTitle}>보유 종목</Text>
        </View>
      }
      ListEmptyComponent={
        !loading ? (
          <View style={styles.centered}>
            <Text style={styles.emptyBody}>보유 중인 종목이 없습니다.</Text>
          </View>
        ) : null
      }
      renderItem={({ item }) => (
        <View style={styles.positionRow}>
          <View style={{ flex: 1 }}>
            <Text style={styles.positionTitle}>{item.name ? `${item.name} (${item.ticker})` : item.ticker}</Text>
            <Text style={styles.positionDetail}>
              {formatNumber(item.qty, 2)}주 · 평단 {formatNumber(item.avg_cost)}
              {item.market === 'US' ? '$' : '원'}
              {item.current_price != null ? ` · 현재가 ${formatNumber(item.current_price)}` : ' · 현재가 조회 실패'}
            </Text>
          </View>
          <Text
            style={[
              styles.positionPnl,
              item.unrealized_pnl != null && item.unrealized_pnl >= 0 ? styles.positive : styles.negative,
            ]}
          >
            {item.unrealized_pnl != null ? `${formatSigned(item.unrealized_pnl)}원` : '-'}
          </Text>
        </View>
      )}
    />
  );
}

function SummaryCard({ label, value, positive }: { label: string; value: string; positive?: boolean }) {
  return (
    <View style={styles.card}>
      <Text style={styles.cardLabel}>{label}</Text>
      <Text style={[styles.cardValue, positive === true && styles.positive, positive === false && styles.negative]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: '#f9fafb' },
  centered: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32 },
  emptyTitle: { fontSize: 16, fontWeight: '600', color: '#374151', marginBottom: 6 },
  emptyBody: { fontSize: 14, color: '#6b7280', textAlign: 'center' },
  errorBanner: { backgroundColor: '#fee2e2', padding: 10, margin: 12, borderRadius: 8 },
  errorText: { color: '#b91c1c', fontSize: 13 },
  summaryGrid: {
    flexDirection: 'row',
    flexWrap: 'wrap',
    padding: 12,
    gap: 12,
  },
  card: {
    flexBasis: '46%',
    flexGrow: 1,
    backgroundColor: '#fff',
    borderRadius: 12,
    padding: 14,
  },
  cardLabel: { fontSize: 12, color: '#6b7280', marginBottom: 6 },
  cardValue: { fontSize: 18, fontWeight: '700', color: '#111827' },
  positive: { color: '#b91c1c' },
  negative: { color: '#1d4ed8' },
  sectionTitle: { fontSize: 14, fontWeight: '600', color: '#374151', marginTop: 8, marginHorizontal: 16, marginBottom: 4 },
  positionRow: {
    flexDirection: 'row',
    alignItems: 'center',
    backgroundColor: '#fff',
    marginHorizontal: 12,
    marginBottom: 8,
    padding: 14,
    borderRadius: 10,
  },
  positionTitle: { fontSize: 15, fontWeight: '600', color: '#111827' },
  positionDetail: { fontSize: 12, color: '#6b7280', marginTop: 4 },
  positionPnl: { fontSize: 15, fontWeight: '700' },
});
