export type Market = 'KR' | 'US';
export type Side = 'BUY' | 'SELL';

export interface Trade {
  id: number;
  ticker: string;
  name: string | null;
  market: Market;
  side: Side;
  quantity: number;
  price: number;
  fee: number;
  tax: number;
  fx_rate: number | null;
  trade_date: string;
  strategy_tag: string | null;
  thesis: string | null;
  created_at: string;
}

export type TradeInput = Omit<Trade, 'id' | 'created_at'>;

export interface Position {
  ticker: string;
  name: string | null;
  market: Market;
  qty: number;
  avg_cost: number;
  current_price: number | null;
  realized_pnl: number;
  unrealized_pnl: number | null;
}

export interface Summary {
  win_rate: number | null;
  total_realized_pnl: number;
  total_unrealized_pnl: number;
  trade_count: number;
}
