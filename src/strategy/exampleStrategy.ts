import { EventEmitter } from 'events';
import { Ticker } from '../kite/ticker';
import { OptionsDataCache } from '../options/dataCache';
import { calculateGreeks, calculateTimeToExpiry } from '../options/greeks';
import { logger } from '../utils/logger';
import { TickData, TradeSignal, OptionsChain } from '../types';

/**
 * Example Options Strategy
 *
 * Strategy Logic:
 * 1. Subscribe to underlying (e.g., NIFTY) and nearby ATM CE/PE options
 * 2. Track underlying price movements
 * 3. Generate BUY signal when:
 *    - Underlying moves > threshold points in < time window
 *    - Option delta > minimum threshold
 * 4. Generate SELL signal when:
 *    - Position profit > target OR
 *    - Position loss > stop loss
 *
 * This is a simplified example for demonstration purposes
 */

export interface StrategyConfig {
  underlying: string;
  underlyingToken: number;
  priceThreshold: number; // Points movement to trigger signal
  timeWindowSeconds: number; // Time window for price movement
  minDelta: number; // Minimum delta for option selection
  targetProfitPercent: number;
  stopLossPercent: number;
  riskFreeRate: number;
  volatility: number; // Assumed volatility if IV not available
}

interface PricePoint {
  price: number;
  timestamp: number;
}

export class ExampleStrategy extends EventEmitter {
  private config: StrategyConfig;
  private ticker: Ticker;
  private dataCache: OptionsDataCache;
  private priceHistory: PricePoint[] = [];
  private currentSpotPrice: number = 0;
  private activeChain: OptionsChain | null = null;
  private positions: Map<
    number,
    { entry: number; quantity: number; signal: TradeSignal }
  > = new Map();

  constructor(
    config: StrategyConfig,
    ticker: Ticker,
    dataCache: OptionsDataCache
  ) {
    super();
    this.config = config;
    this.ticker = ticker;
    this.dataCache = dataCache;

    logger.info('ExampleStrategy initialized', {
      underlying: config.underlying,
      priceThreshold: config.priceThreshold,
      timeWindow: config.timeWindowSeconds,
    });
  }

  /**
   * Start the strategy
   */
  async start(): Promise<void> {
    logger.info('Starting strategy');

    // Subscribe to underlying
    this.ticker.subscribe([this.config.underlyingToken], 'quote');

    // Listen to tick events
    this.ticker.on('tick', (tick: TickData) => {
      this.onTick(tick);
    });

    logger.info('Strategy started, listening for ticks');
  }

  /**
   * Stop the strategy
   */
  stop(): void {
    logger.info('Stopping strategy');

    // Unsubscribe from all instruments
    this.ticker.unsubscribe([this.config.underlyingToken]);

    // Remove listeners
    this.ticker.removeAllListeners('tick');

    logger.info('Strategy stopped');
  }

  /**
   * Handle incoming ticks
   */
  private onTick(tick: TickData): void {
    // Check if this is the underlying
    if (tick.instrumentToken === this.config.underlyingToken) {
      this.handleUnderlyingTick(tick);
    } else {
      // This is an option tick
      this.handleOptionTick(tick);
    }
  }

  /**
   * Handle underlying price tick
   */
  private handleUnderlyingTick(tick: TickData): void {
    this.currentSpotPrice = tick.lastPrice;

    // Update price history
    this.priceHistory.push({
      price: tick.lastPrice,
      timestamp: tick.timestamp.getTime(),
    });

    // Keep only recent history (time window + buffer)
    const cutoffTime =
      Date.now() - this.config.timeWindowSeconds * 1000 - 10000;
    this.priceHistory = this.priceHistory.filter(
      (p) => p.timestamp > cutoffTime
    );

    logger.debug('Underlying tick', {
      price: tick.lastPrice,
      historySize: this.priceHistory.length,
    });

    // Check for price movement signal
    this.checkPriceMovement();
  }

  /**
   * Handle option price tick
   */
  private handleOptionTick(tick: TickData): void {
    logger.debug('Option tick', {
      token: tick.instrumentToken,
      price: tick.lastPrice,
    });

    // Check positions for profit/loss targets
    const position = this.positions.get(tick.instrumentToken);

    if (position) {
      this.checkPositionTargets(tick, position);
    }
  }

  /**
   * Check for significant price movement
   */
  private checkPriceMovement(): void {
    if (this.priceHistory.length < 2) {
      return;
    }

    const now = Date.now();
    const windowStart = now - this.config.timeWindowSeconds * 1000;

    // Get prices within time window
    const recentPrices = this.priceHistory.filter(
      (p) => p.timestamp >= windowStart
    );

    if (recentPrices.length < 2) {
      return;
    }

    const oldestPrice = recentPrices[0].price;
    const currentPrice = this.currentSpotPrice;
    const priceChange = Math.abs(currentPrice - oldestPrice);

    logger.debug('Price movement check', {
      oldestPrice,
      currentPrice,
      priceChange,
      threshold: this.config.priceThreshold,
    });

    if (priceChange >= this.config.priceThreshold) {
      const direction = currentPrice > oldestPrice ? 'UP' : 'DOWN';

      logger.info('Significant price movement detected', {
        direction,
        change: priceChange,
        threshold: this.config.priceThreshold,
      });

      // Generate trade signal
      this.generateTradeSignal(direction, priceChange);
    }
  }

  /**
   * Generate trade signal based on price movement
   */
  private generateTradeSignal(
    direction: 'UP' | 'DOWN',
    priceChange: number
  ): void {
    // For upward movement, buy call options
    // For downward movement, buy put options
    const optionType = direction === 'UP' ? 'CE' : 'PE';

    logger.info('Generating trade signal', {
      direction,
      optionType,
      spotPrice: this.currentSpotPrice,
    });

    // In a real implementation, you would:
    // 1. Fetch current options chain
    // 2. Select appropriate strike (e.g., ATM or slightly OTM)
    // 3. Calculate Greeks
    // 4. Check if delta meets minimum threshold
    // 5. Emit trade signal

    // For this example, we'll emit a simplified signal
    const signal: TradeSignal = {
      symbol: `${this.config.underlying}-${optionType}`,
      instrumentToken: 0, // Would be actual token
      action: 'BUY',
      quantity: 1, // Lot size
      reason: `Price moved ${direction} by ${priceChange.toFixed(2)} points in ${this.config.timeWindowSeconds}s`,
      confidence: Math.min(priceChange / this.config.priceThreshold, 1),
      timestamp: new Date(),
      metadata: {
        direction,
        priceChange,
        spotPrice: this.currentSpotPrice,
        optionType,
      },
    };

    logger.info('Trade signal generated', signal);
    this.emit('signal', signal);
  }

  /**
   * Check position targets (profit/stop loss)
   */
  private checkPositionTargets(
    tick: TickData,
    position: {
      entry: number;
      quantity: number;
      signal: TradeSignal;
    }
  ): void {
    const currentPrice = tick.lastPrice;
    const entryPrice = position.entry;
    const pnlPercent = ((currentPrice - entryPrice) / entryPrice) * 100;

    logger.debug('Checking position targets', {
      symbol: tick.tradingSymbol,
      entry: entryPrice,
      current: currentPrice,
      pnlPercent,
    });

    // Check profit target
    if (pnlPercent >= this.config.targetProfitPercent) {
      logger.info('Profit target hit', {
        symbol: tick.tradingSymbol,
        pnlPercent,
        target: this.config.targetProfitPercent,
      });

      this.generateExitSignal(tick, position, 'PROFIT_TARGET');
    }
    // Check stop loss
    else if (pnlPercent <= -this.config.stopLossPercent) {
      logger.info('Stop loss hit', {
        symbol: tick.tradingSymbol,
        pnlPercent,
        stopLoss: this.config.stopLossPercent,
      });

      this.generateExitSignal(tick, position, 'STOP_LOSS');
    }
  }

  /**
   * Generate exit signal
   */
  private generateExitSignal(
    tick: TickData,
    position: {
      entry: number;
      quantity: number;
      signal: TradeSignal;
    },
    reason: string
  ): void {
    const signal: TradeSignal = {
      symbol: tick.tradingSymbol || '',
      instrumentToken: tick.instrumentToken,
      action: 'SELL',
      quantity: position.quantity,
      reason,
      confidence: 1,
      timestamp: new Date(),
      metadata: {
        entryPrice: position.entry,
        exitPrice: tick.lastPrice,
        pnl: (tick.lastPrice - position.entry) * position.quantity,
      },
    };

    logger.info('Exit signal generated', signal);
    this.emit('signal', signal);

    // Remove position
    this.positions.delete(tick.instrumentToken);
  }

  /**
   * Record a position (called after order execution)
   */
  recordPosition(
    instrumentToken: number,
    entryPrice: number,
    quantity: number,
    signal: TradeSignal
  ): void {
    this.positions.set(instrumentToken, {
      entry: entryPrice,
      quantity,
      signal,
    });

    logger.info('Position recorded', {
      instrumentToken,
      entryPrice,
      quantity,
    });
  }

  /**
   * Get current positions
   */
  getPositions(): Map<
    number,
    { entry: number; quantity: number; signal: TradeSignal }
  > {
    return this.positions;
  }

  /**
   * Get strategy status
   */
  getStatus(): {
    spotPrice: number;
    priceHistorySize: number;
    activePositions: number;
  } {
    return {
      spotPrice: this.currentSpotPrice,
      priceHistorySize: this.priceHistory.length,
      activePositions: this.positions.size,
    };
  }
}

export default ExampleStrategy;
