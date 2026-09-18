export function formatNumber(value: number, fractionDigits = 0): string {
  return value.toLocaleString('ko-KR', {
    minimumFractionDigits: fractionDigits,
    maximumFractionDigits: fractionDigits,
  });
}

export function formatSigned(value: number, fractionDigits = 0): string {
  const sign = value > 0 ? '+' : '';
  return `${sign}${formatNumber(value, fractionDigits)}`;
}

export function formatPercent(ratio: number | null, fractionDigits = 1): string {
  if (ratio == null) return '-';
  return `${(ratio * 100).toFixed(fractionDigits)}%`;
}
