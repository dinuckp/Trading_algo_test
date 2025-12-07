/**
 * Type definitions for Kite objects and application interfaces
 */

// Kite order types
export type OrderType = 'MARKET' | 'LIMIT' | 'SL' | 'SL-M';
export type TransactionType = 'BUY' | 'SELL';
export type ProductType = 'CNC' | 'NRML' | 'MIS';
export type OrderVariety = 'regular' | 'amo' | 'co' | 'iceberg';
export type OrderStatus =
  | 'PENDING'
  | 'OPEN'
  | 'COMPLETE'
  | 'CANCELLED'
  | 'REJECTED'
  | 'FAILED';

export interface KiteTokens {
  accessToken: string;
  refreshToken?: string;
  expiresAt?: number;
}

export interface KiteProfile {
  user_id: string;
  user_name: string;
  email: string;
  user_type: string;
  broker: string;
}

export interface TickData {
  instrumentToken: number;
  tradingSymbol?: string;
  lastPrice: number;
  timestamp: Date;
  volume?: number;
  oi?: number;
  buyQuantity?: number;
  sellQuantity?: number;
  lastTradedQuantity?: number;
  averagePrice?: number;
  ohlc?: {
    open: number;
    high: number;
    low: number;
    close: number;
  };
  depth?: {
    buy: Array<{ price: number; quantity: number; orders: number }>;
    sell: Array<{ price: number; quantity: number; orders: number }>;
  };
}

export interface OrderIntent {
  symbol: string;
  instrumentToken: number;
  exchange: string;
  transactionType: TransactionType;
  quantity: number;
  orderType: OrderType;
  price?: number;
  triggerPrice?: number;
  product: ProductType;
  variety: OrderVariety;
  validity?: 'DAY' | 'IOC';
  disclosedQuantity?: number;
  tag?: string;
}

export interface OrderResult {
  success: boolean;
  orderId?: string;
  message?: string;
  error?: string;
  timestamp: Date;
  mock?: boolean;
}

export interface Position {
  tradingSymbol: string;
  exchange: string;
  instrumentToken: number;
  product: ProductType;
  quantity: number;
  buyQuantity: number;
  sellQuantity: number;
  averagePrice: number;
  lastPrice: number;
  pnl: number;
  unrealizedPnl: number;
  realizedPnl: number;
  value: number;
  closePrice: number;
  buyPrice: number;
  sellPrice: number;
  buyValue: number;
  sellValue: number;
  multiplier: number;
  overnightQuantity: number;
  dayBuyQuantity: number;
  daySellQuantity: number;
}

export interface Holding {
  tradingSymbol: string;
  exchange: string;
  instrumentToken: number;
  isin: string;
  product: ProductType;
  quantity: number;
  t1Quantity: number;
  averagePrice: number;
  lastPrice: number;
  pnl: number;
  collateralQuantity: number;
  collateralType: string;
}

export interface Instrument {
  instrumentToken: number;
  exchangeToken: number;
  tradingSymbol: string;
  name: string;
  lastPrice: number;
  expiry: Date | null;
  strike: number;
  tickSize: number;
  lotSize: number;
  instrumentType: 'EQ' | 'FUT' | 'CE' | 'PE';
  segment: string;
  exchange: string;
}

export interface OptionInstrument extends Instrument {
  instrumentType: 'CE' | 'PE';
  expiry: Date;
  strike: number;
  underlying: string;
}

export interface Greeks {
  delta: number;
  gamma: number;
  theta: number;
  vega: number;
  rho: number;
}

export interface OptionChainEntry {
  instrument: OptionInstrument;
  greeks?: Greeks;
  iv?: number; // Implied volatility
  lastPrice: number;
  bid?: number;
  ask?: number;
  oi?: number;
  volume?: number;
  cachedAt: Date;
}

export interface OptionsChain {
  underlying: string;
  spotPrice: number;
  expiry: Date;
  strikes: Map<number, { call?: OptionChainEntry; put?: OptionChainEntry }>;
  updatedAt: Date;
}

export interface TradeSignal {
  symbol: string;
  instrumentToken: number;
  action: 'BUY' | 'SELL' | 'CLOSE';
  quantity: number;
  reason: string;
  confidence: number;
  timestamp: Date;
  metadata?: Record<string, unknown>;
}

export interface BacktestTick {
  timestamp: Date;
  symbol: string;
  open: number;
  high: number;
  low: number;
  close: number;
  volume: number;
  oi?: number;
}

export interface BacktestResult {
  totalTrades: number;
  winningTrades: number;
  losingTrades: number;
  totalPnl: number;
  maxDrawdown: number;
  sharpeRatio: number;
  winRate: number;
  avgWin: number;
  avgLoss: number;
  profitFactor: number;
  trades: Array<{
    entryTime: Date;
    exitTime: Date;
    symbol: string;
    side: 'BUY' | 'SELL';
    entryPrice: number;
    exitPrice: number;
    quantity: number;
    pnl: number;
  }>;
}

export interface RiskCheckResult {
  allowed: boolean;
  reason?: string;
  checks: {
    totalExposure: { passed: boolean; current: number; limit: number };
    tradeRisk: { passed: boolean; current: number; limit: number };
    positionSize: { passed: boolean; current: number; limit: number };
    vegaExposure?: { passed: boolean; current: number; limit: number };
    deltaExposure?: { passed: boolean; current: number; limit: number };
    marginAvailable?: { passed: boolean; current: number; required: number };
  };
}

export interface ThrottleResult {
  allowed: boolean;
  retryAfter?: number; // milliseconds
  reason?: string;
}
