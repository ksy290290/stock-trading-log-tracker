import { ReactNode, useState } from 'react';
import {
  Alert,
  KeyboardAvoidingView,
  Platform,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  TouchableOpacity,
  View,
} from 'react-native';

import { Market, Side, Trade, TradeInput } from '../types';
import { SegmentedControl } from './SegmentedControl';

function todayIso() {
  return new Date().toISOString().slice(0, 10);
}

function toNumber(text: string): number {
  const n = Number(text.replace(/,/g, ''));
  return Number.isFinite(n) ? n : 0;
}

interface Props {
  initial?: Trade;
  submitLabel: string;
  submitting: boolean;
  onSubmit: (input: TradeInput) => void;
  onDelete?: () => void;
}

export function TradeForm({ initial, submitLabel, submitting, onSubmit, onDelete }: Props) {
  const [ticker, setTicker] = useState(initial?.ticker ?? '');
  const [name, setName] = useState(initial?.name ?? '');
  const [market, setMarket] = useState<Market>(initial?.market ?? 'KR');
  const [side, setSide] = useState<Side>(initial?.side ?? 'BUY');
  const [quantity, setQuantity] = useState(initial ? String(initial.quantity) : '');
  const [price, setPrice] = useState(initial ? String(initial.price) : '');
  const [fee, setFee] = useState(initial ? String(initial.fee) : '0');
  const [tax, setTax] = useState(initial ? String(initial.tax) : '0');
  const [fxRate, setFxRate] = useState(initial?.fx_rate != null ? String(initial.fx_rate) : '');
  const [tradeDate, setTradeDate] = useState(initial?.trade_date ?? todayIso());
  const [strategyTag, setStrategyTag] = useState(initial?.strategy_tag ?? '');
  const [thesis, setThesis] = useState(initial?.thesis ?? '');

  const handleSubmit = () => {
    if (!ticker.trim()) {
      Alert.alert('입력 확인', '종목 코드를 입력해주세요.');
      return;
    }
    if (!/^\d{4}-\d{2}-\d{2}$/.test(tradeDate)) {
      Alert.alert('입력 확인', '거래일은 YYYY-MM-DD 형식으로 입력해주세요.');
      return;
    }
    const qty = toNumber(quantity);
    const prc = toNumber(price);
    if (qty <= 0 || prc <= 0) {
      Alert.alert('입력 확인', '수량과 가격은 0보다 커야 합니다.');
      return;
    }
    onSubmit({
      ticker: ticker.trim(),
      name: name.trim() || null,
      market,
      side,
      quantity: qty,
      price: prc,
      fee: toNumber(fee),
      tax: toNumber(tax),
      fx_rate: market === 'US' && fxRate.trim() ? toNumber(fxRate) : null,
      trade_date: tradeDate,
      strategy_tag: strategyTag.trim() || null,
      thesis: thesis.trim() || null,
    });
  };

  return (
    <KeyboardAvoidingView
      style={{ flex: 1 }}
      behavior={Platform.OS === 'ios' ? 'padding' : undefined}
    >
      <ScrollView contentContainerStyle={styles.container} keyboardShouldPersistTaps="handled">
        <Field label="시장">
          <SegmentedControl
            options={[
              { label: '국내', value: 'KR' },
              { label: '해외', value: 'US' },
            ]}
            value={market}
            onChange={setMarket}
          />
        </Field>

        <Field label="매매 구분">
          <SegmentedControl
            options={[
              { label: '매수', value: 'BUY' },
              { label: '매도', value: 'SELL' },
            ]}
            value={side}
            onChange={setSide}
          />
        </Field>

        <Field label="종목 코드">
          <TextInput
            style={styles.input}
            value={ticker}
            onChangeText={setTicker}
            placeholder={market === 'KR' ? '예: 005930' : '예: AAPL'}
            autoCapitalize="characters"
          />
        </Field>

        <Field label="종목명 (선택)">
          <TextInput style={styles.input} value={name} onChangeText={setName} placeholder="예: 삼성전자" />
        </Field>

        <View style={styles.row}>
          <Field label="수량" style={styles.rowItem}>
            <TextInput
              style={styles.input}
              value={quantity}
              onChangeText={setQuantity}
              keyboardType="decimal-pad"
              placeholder="0"
            />
          </Field>
          <Field label="가격" style={styles.rowItem}>
            <TextInput
              style={styles.input}
              value={price}
              onChangeText={setPrice}
              keyboardType="decimal-pad"
              placeholder="0"
            />
          </Field>
        </View>

        <View style={styles.row}>
          <Field label="수수료" style={styles.rowItem}>
            <TextInput style={styles.input} value={fee} onChangeText={setFee} keyboardType="decimal-pad" />
          </Field>
          <Field label="세금" style={styles.rowItem}>
            <TextInput style={styles.input} value={tax} onChangeText={setTax} keyboardType="decimal-pad" />
          </Field>
        </View>

        {market === 'US' && (
          <Field label="체결 시점 환율 (선택)">
            <TextInput
              style={styles.input}
              value={fxRate}
              onChangeText={setFxRate}
              keyboardType="decimal-pad"
              placeholder="예: 1380.5"
            />
          </Field>
        )}

        <Field label="거래일 (YYYY-MM-DD)">
          <TextInput style={styles.input} value={tradeDate} onChangeText={setTradeDate} placeholder={todayIso()} />
        </Field>

        <Field label="전략 태그 (선택)">
          <TextInput style={styles.input} value={strategyTag} onChangeText={setStrategyTag} placeholder="예: 장기" />
        </Field>

        <Field label="매매 사유 (선택)">
          <TextInput
            style={[styles.input, styles.multiline]}
            value={thesis}
            onChangeText={setThesis}
            placeholder="매수/매도 이유를 적어두세요"
            multiline
          />
        </Field>

        <TouchableOpacity
          style={[styles.submitButton, submitting && styles.disabled]}
          onPress={handleSubmit}
          disabled={submitting}
        >
          <Text style={styles.submitLabel}>{submitting ? '저장 중...' : submitLabel}</Text>
        </TouchableOpacity>

        {onDelete && (
          <TouchableOpacity style={styles.deleteButton} onPress={onDelete} disabled={submitting}>
            <Text style={styles.deleteLabel}>이 기록 삭제</Text>
          </TouchableOpacity>
        )}
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

function Field({ label, children, style }: { label: string; children: ReactNode; style?: object }) {
  return (
    <View style={[styles.field, style]}>
      <Text style={styles.fieldLabel}>{label}</Text>
      {children}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    padding: 16,
    paddingBottom: 48,
    gap: 4,
  },
  field: {
    marginBottom: 14,
  },
  fieldLabel: {
    fontSize: 13,
    color: '#6b7280',
    marginBottom: 6,
    fontWeight: '500',
  },
  input: {
    borderWidth: 1,
    borderColor: '#d1d5db',
    borderRadius: 8,
    paddingHorizontal: 12,
    paddingVertical: 10,
    fontSize: 16,
    backgroundColor: '#fff',
  },
  multiline: {
    minHeight: 80,
    textAlignVertical: 'top',
  },
  row: {
    flexDirection: 'row',
    gap: 12,
  },
  rowItem: {
    flex: 1,
  },
  submitButton: {
    backgroundColor: '#2563eb',
    borderRadius: 10,
    paddingVertical: 14,
    alignItems: 'center',
    marginTop: 8,
  },
  disabled: {
    opacity: 0.6,
  },
  submitLabel: {
    color: '#fff',
    fontSize: 16,
    fontWeight: '600',
  },
  deleteButton: {
    marginTop: 12,
    paddingVertical: 14,
    alignItems: 'center',
  },
  deleteLabel: {
    color: '#dc2626',
    fontSize: 15,
    fontWeight: '600',
  },
});
