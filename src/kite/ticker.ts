import { KiteTicker } from 'kiteconnect';
import { EventEmitter } from 'events';
import { config } from '../config';
import { logger } from '../utils/logger';
import { TickData } from '../types';

/**
 * KiteTicker - WebSocket wrapper for Kite Ticker
 * Features:
 * - Normalized tick events
 * - Automatic reconnection with exponential backoff
 * - Subscription preservation across reconnects
 * - Error handling and logging
 */

export interface TickerOptions {
  apiKey: string;
  accessToken: string;
  reconnectMaxDelay?: number;
  reconnectMaxTries?: number;
}

export class Ticker extends EventEmitter {
  private ticker: KiteTicker;
  private subscriptions: Set<number> = new Set();
  private mode: Map<number, string> = new Map(); // 'quote', 'full', or 'ltp'
  private reconnectAttempts = 0;
  private reconnectDelay = 1000; // Start with 1 second
  private maxReconnectDelay: number;
  private maxReconnectTries: number;
  private isConnected = false;
  private shouldReconnect = true;

  constructor(options: TickerOptions) {
    super();

    if (!options.apiKey || !options.accessToken) {
      throw new Error('API key and access token are required');
    }

    this.maxReconnectDelay =
      options.reconnectMaxDelay || config.websocket.reconnectMaxDelay;
    this.maxReconnectTries =
      options.reconnectMaxTries || config.websocket.reconnectMaxTries;

    this.ticker = new KiteTicker({
      api_key: options.apiKey,
      access_token: options.accessToken,
    });

    this.setupEventHandlers();

    logger.info('Ticker initialized');
  }

  /**
   * Setup event handlers for the ticker
   */
  private setupEventHandlers(): void {
    this.ticker.on('connect', () => {
      this.isConnected = true;
      this.reconnectAttempts = 0;
      this.reconnectDelay = 1000;

      logger.info('WebSocket connected');
      this.emit('connect');

      // Restore subscriptions after reconnect
      if (this.subscriptions.size > 0) {
        this.restoreSubscriptions();
      }
    });

    this.ticker.on('disconnect', (error: Error) => {
      this.isConnected = false;
      logger.warn('WebSocket disconnected', { error: error?.message });
      this.emit('disconnect', error);

      // Attempt to reconnect
      if (this.shouldReconnect) {
        this.attemptReconnect();
      }
    });

    this.ticker.on('error', (error: Error) => {
      logger.error('WebSocket error', { error: error?.message });
      this.emit('error', error);
    });

    this.ticker.on('close', (code: number, reason: string) => {
      this.isConnected = false;
      logger.info('WebSocket closed', { code, reason });
      this.emit('close', code, reason);
    });

    this.ticker.on('ticks', (ticks: unknown[]) => {
      try {
        const normalizedTicks = this.normalizeTicks(ticks);
        this.emit('ticks', normalizedTicks);

        // Emit individual tick events
        for (const tick of normalizedTicks) {
          this.emit('tick', tick);
        }
      } catch (error) {
        logger.error('Error processing ticks', { error });
      }
    });

    this.ticker.on('order_update', (order: unknown) => {
      logger.info('Order update received', { order });
      this.emit('order_update', order);
    });
  }

  /**
   * Normalize ticks to a consistent format
   */
  private normalizeTicks(ticks: unknown[]): TickData[] {
    return ticks.map((tick: any) => {
      const normalized: TickData = {
        instrumentToken: tick.instrument_token,
        tradingSymbol: tick.tradable ? tick.tradable : undefined,
        lastPrice: tick.last_price,
        timestamp: tick.exchange_timestamp
          ? new Date(tick.exchange_timestamp)
          : new Date(),
        volume: tick.volume,
        oi: tick.oi,
        buyQuantity: tick.buy_quantity,
        sellQuantity: tick.sell_quantity,
        lastTradedQuantity: tick.last_quantity,
        averagePrice: tick.average_price,
      };

      // Add OHLC if available
      if (tick.ohlc) {
        normalized.ohlc = {
          open: tick.ohlc.open,
          high: tick.ohlc.high,
          low: tick.ohlc.low,
          close: tick.ohlc.close,
        };
      }

      // Add depth if available
      if (tick.depth) {
        normalized.depth = {
          buy: tick.depth.buy || [],
          sell: tick.depth.sell || [],
        };
      }

      return normalized;
    });
  }

  /**
   * Attempt reconnection with exponential backoff
   */
  private attemptReconnect(): void {
    if (this.reconnectAttempts >= this.maxReconnectTries) {
      logger.error('Max reconnection attempts reached', {
        attempts: this.reconnectAttempts,
      });
      this.emit('reconnect_failed');
      return;
    }

    this.reconnectAttempts++;

    logger.info('Attempting to reconnect', {
      attempt: this.reconnectAttempts,
      delay: this.reconnectDelay,
    });

    setTimeout(() => {
      if (!this.isConnected && this.shouldReconnect) {
        try {
          this.ticker.connect();
        } catch (error) {
          logger.error('Reconnection attempt failed', { error });
        }
      }
    }, this.reconnectDelay);

    // Exponential backoff
    this.reconnectDelay = Math.min(this.reconnectDelay * 2, this.maxReconnectDelay);
  }

  /**
   * Restore subscriptions after reconnect
   */
  private restoreSubscriptions(): void {
    if (this.subscriptions.size === 0) return;

    const instruments = Array.from(this.subscriptions);

    logger.info('Restoring subscriptions', {
      count: instruments.length,
    });

    try {
      this.ticker.subscribe(instruments);

      // Restore modes
      const fullMode: number[] = [];
      const quoteMode: number[] = [];
      const ltpMode: number[] = [];

      for (const token of instruments) {
        const mode = this.mode.get(token) || 'quote';
        if (mode === 'full') fullMode.push(token);
        else if (mode === 'quote') quoteMode.push(token);
        else ltpMode.push(token);
      }

      if (fullMode.length > 0) this.ticker.setMode(this.ticker.modeFull, fullMode);
      if (quoteMode.length > 0) this.ticker.setMode(this.ticker.modeQuote, quoteMode);
      if (ltpMode.length > 0) this.ticker.setMode(this.ticker.modeLTP, ltpMode);

      logger.info('Subscriptions restored successfully');
    } catch (error) {
      logger.error('Failed to restore subscriptions', { error });
    }
  }

  /**
   * Connect to WebSocket
   */
  connect(): void {
    try {
      logger.info('Connecting to WebSocket');
      this.shouldReconnect = true;
      this.ticker.connect();
    } catch (error) {
      logger.error('Failed to connect', { error });
      throw error;
    }
  }

  /**
   * Disconnect from WebSocket
   */
  disconnect(): void {
    try {
      logger.info('Disconnecting from WebSocket');
      this.shouldReconnect = false;
      this.ticker.disconnect();
    } catch (error) {
      logger.error('Failed to disconnect', { error });
      throw error;
    }
  }

  /**
   * Subscribe to instruments
   */
  subscribe(instruments: number[], mode: 'ltp' | 'quote' | 'full' = 'quote'): void {
    try {
      logger.info('Subscribing to instruments', {
        count: instruments.length,
        mode,
      });

      this.ticker.subscribe(instruments);

      // Set mode
      const modeConstant =
        mode === 'full'
          ? this.ticker.modeFull
          : mode === 'ltp'
          ? this.ticker.modeLTP
          : this.ticker.modeQuote;

      this.ticker.setMode(modeConstant, instruments);

      // Track subscriptions
      for (const token of instruments) {
        this.subscriptions.add(token);
        this.mode.set(token, mode);
      }
    } catch (error) {
      logger.error('Failed to subscribe', { error, instruments });
      throw error;
    }
  }

  /**
   * Unsubscribe from instruments
   */
  unsubscribe(instruments: number[]): void {
    try {
      logger.info('Unsubscribing from instruments', {
        count: instruments.length,
      });

      this.ticker.unsubscribe(instruments);

      // Remove from tracking
      for (const token of instruments) {
        this.subscriptions.delete(token);
        this.mode.delete(token);
      }
    } catch (error) {
      logger.error('Failed to unsubscribe', { error, instruments });
      throw error;
    }
  }

  /**
   * Get current subscriptions
   */
  getSubscriptions(): number[] {
    return Array.from(this.subscriptions);
  }

  /**
   * Check if connected
   */
  isWsConnected(): boolean {
    return this.isConnected;
  }
}

export default Ticker;
