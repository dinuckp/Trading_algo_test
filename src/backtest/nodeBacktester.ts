import fs from 'fs';
import { logger } from '../utils/logger';
import { BacktestTick, BacktestResult, TradeSignal } from '../types';

/**
 * Simple Node.js Backtester
 *
 * Accepts historical tick data and trade signals
 * Simulates order fills and calculates P&L
 * Useful for quick backtests without Python dependency
 */

interface Trade {
  entryTime: Date;
  exitTime: Date;
  symbol: string;
  side: 'BUY' | 'SELL';
  entryPrice: number;
  exitPrice: number;
  quantity: number;
  pnl: number;
}

export interface BacktestConfig {
  initialCash: number;
  commission: number; // Per trade
  slippage: number; // Percentage
}

export class NodeBacktester {
  private config: BacktestConfig;
  private cash: number;
  private positions: Map<
    string,
    { price: number; quantity: number; time: Date }
  > = new Map();
  private trades: Trade[] = [];
  private equity: number[];
  private maxEquity: number;

  constructor(customConfig?: Partial<BacktestConfig>) {
    this.config = {
      initialCash: customConfig?.initialCash || 100000,
      commission: customConfig?.commission || 20,
      slippage: customConfig?.slippage || 0.001, // 0.1%
    };

    this.cash = this.config.initialCash;
    this.equity = [this.config.initialCash];
    this.maxEquity = this.config.initialCash;

    logger.info('NodeBacktester initialized', {
      initialCash: this.config.initialCash,
      commission: this.config.commission,
      slippage: this.config.slippage,
    });
  }

  /**
   * Load historical data from CSV file
   */
  loadDataFromCSV(filePath: string): BacktestTick[] {
    logger.info('Loading historical data', { filePath });

    const content = fs.readFileSync(filePath, 'utf-8');
    const lines = content.trim().split('\n');
    const headers = lines[0].split(',');

    const ticks: BacktestTick[] = [];

    for (let i = 1; i < lines.length; i++) {
      const values = lines[i].split(',');

      const tick: BacktestTick = {
        timestamp: new Date(values[0]),
        symbol: values[1],
        open: parseFloat(values[2]),
        high: parseFloat(values[3]),
        low: parseFloat(values[4]),
        close: parseFloat(values[5]),
        volume: parseFloat(values[6]),
        oi: values[7] ? parseFloat(values[7]) : undefined,
      };

      ticks.push(tick);
    }

    logger.info('Historical data loaded', { tickCount: ticks.length });
    return ticks;
  }

  /**
   * Run backtest with historical data and signals
   */
  runBacktest(
    ticks: BacktestTick[],
    signals: TradeSignal[]
  ): BacktestResult {
    logger.info('Running backtest', {
      tickCount: ticks.length,
      signalCount: signals.length,
    });

    // Sort ticks by timestamp
    const sortedTicks = [...ticks].sort(
      (a, b) => a.timestamp.getTime() - b.timestamp.getTime()
    );

    // Create a map of ticks by timestamp for quick lookup
    const tickMap = new Map<number, BacktestTick[]>();
    for (const tick of sortedTicks) {
      const key = tick.timestamp.getTime();
      if (!tickMap.has(key)) {
        tickMap.set(key, []);
      }
      tickMap.get(key)!.push(tick);
    }

    // Process signals in chronological order
    const sortedSignals = [...signals].sort(
      (a, b) => a.timestamp.getTime() - b.timestamp.getTime()
    );

    for (const signal of sortedSignals) {
      // Find corresponding tick data
      const tick = this.findClosestTick(
        signal.symbol,
        signal.timestamp,
        sortedTicks
      );

      if (!tick) {
        logger.warn('No tick data found for signal', {
          symbol: signal.symbol,
          timestamp: signal.timestamp,
        });
        continue;
      }

      // Process signal
      if (signal.action === 'BUY') {
        this.executeBuy(signal, tick);
      } else if (signal.action === 'SELL' || signal.action === 'CLOSE') {
        this.executeSell(signal, tick);
      }

      // Update equity
      this.updateEquity(tick);
    }

    // Calculate results
    const result = this.calculateResults();

    logger.info('Backtest completed', {
      totalTrades: result.totalTrades,
      totalPnl: result.totalPnl,
      winRate: result.winRate,
    });

    return result;
  }

  /**
   * Execute a buy signal
   */
  private executeBuy(signal: TradeSignal, tick: BacktestTick): void {
    // Calculate execution price with slippage
    const executionPrice = tick.close * (1 + this.config.slippage);
    const cost = executionPrice * signal.quantity + this.config.commission;

    if (cost > this.cash) {
      logger.warn('Insufficient cash for buy', {
        required: cost,
        available: this.cash,
      });
      return;
    }

    // Deduct cash
    this.cash -= cost;

    // Add or update position
    const existing = this.positions.get(signal.symbol);
    if (existing) {
      // Average price
      const totalQuantity = existing.quantity + signal.quantity;
      const avgPrice =
        (existing.price * existing.quantity +
          executionPrice * signal.quantity) /
        totalQuantity;

      this.positions.set(signal.symbol, {
        price: avgPrice,
        quantity: totalQuantity,
        time: tick.timestamp,
      });
    } else {
      this.positions.set(signal.symbol, {
        price: executionPrice,
        quantity: signal.quantity,
        time: tick.timestamp,
      });
    }

    logger.debug('Buy executed', {
      symbol: signal.symbol,
      quantity: signal.quantity,
      price: executionPrice,
    });
  }

  /**
   * Execute a sell signal
   */
  private executeSell(signal: TradeSignal, tick: BacktestTick): void {
    const position = this.positions.get(signal.symbol);

    if (!position) {
      logger.warn('No position to sell', { symbol: signal.symbol });
      return;
    }

    // Calculate execution price with slippage
    const executionPrice = tick.close * (1 - this.config.slippage);
    const sellQuantity = Math.min(signal.quantity, position.quantity);

    // Calculate P&L
    const pnl =
      (executionPrice - position.price) * sellQuantity -
      this.config.commission;

    // Add cash
    this.cash += executionPrice * sellQuantity - this.config.commission;

    // Record trade
    const trade: Trade = {
      entryTime: position.time,
      exitTime: tick.timestamp,
      symbol: signal.symbol,
      side: 'BUY',
      entryPrice: position.price,
      exitPrice: executionPrice,
      quantity: sellQuantity,
      pnl,
    };

    this.trades.push(trade);

    // Update or remove position
    if (sellQuantity >= position.quantity) {
      this.positions.delete(signal.symbol);
    } else {
      position.quantity -= sellQuantity;
    }

    logger.debug('Sell executed', {
      symbol: signal.symbol,
      quantity: sellQuantity,
      price: executionPrice,
      pnl,
    });
  }

  /**
   * Update equity based on current positions
   */
  private updateEquity(tick: BacktestTick): void {
    let positionValue = 0;

    for (const [symbol, position] of this.positions) {
      // Use current tick price if available, otherwise use entry price
      const currentPrice =
        symbol === tick.symbol ? tick.close : position.price;
      positionValue += currentPrice * position.quantity;
    }

    const totalEquity = this.cash + positionValue;
    this.equity.push(totalEquity);

    if (totalEquity > this.maxEquity) {
      this.maxEquity = totalEquity;
    }
  }

  /**
   * Find closest tick for a given symbol and time
   */
  private findClosestTick(
    symbol: string,
    timestamp: Date,
    ticks: BacktestTick[]
  ): BacktestTick | null {
    const targetTime = timestamp.getTime();

    let closest: BacktestTick | null = null;
    let minDiff = Infinity;

    for (const tick of ticks) {
      if (tick.symbol !== symbol) continue;

      const diff = Math.abs(tick.timestamp.getTime() - targetTime);

      if (diff < minDiff) {
        minDiff = diff;
        closest = tick;
      }

      // If we've gone past the target time, break
      if (tick.timestamp.getTime() > targetTime) {
        break;
      }
    }

    return closest;
  }

  /**
   * Calculate backtest results
   */
  private calculateResults(): BacktestResult {
    const totalTrades = this.trades.length;
    const winningTrades = this.trades.filter((t) => t.pnl > 0).length;
    const losingTrades = this.trades.filter((t) => t.pnl <= 0).length;

    const totalPnl = this.trades.reduce((sum, t) => sum + t.pnl, 0);
    const wins = this.trades.filter((t) => t.pnl > 0);
    const losses = this.trades.filter((t) => t.pnl <= 0);

    const avgWin = wins.length > 0 ? wins.reduce((sum, t) => sum + t.pnl, 0) / wins.length : 0;
    const avgLoss = losses.length > 0 ? Math.abs(losses.reduce((sum, t) => sum + t.pnl, 0) / losses.length) : 0;

    const winRate = totalTrades > 0 ? winningTrades / totalTrades : 0;
    const profitFactor = avgLoss > 0 ? avgWin / avgLoss : 0;

    // Calculate max drawdown
    let maxDrawdown = 0;
    for (let i = 0; i < this.equity.length; i++) {
      const drawdown = (this.maxEquity - this.equity[i]) / this.maxEquity;
      maxDrawdown = Math.max(maxDrawdown, drawdown);
    }

    // Calculate Sharpe ratio (simplified)
    const returns = [];
    for (let i = 1; i < this.equity.length; i++) {
      returns.push((this.equity[i] - this.equity[i - 1]) / this.equity[i - 1]);
    }

    const avgReturn =
      returns.length > 0 ? returns.reduce((sum, r) => sum + r, 0) / returns.length : 0;
    const variance =
      returns.length > 0
        ? returns.reduce((sum, r) => sum + Math.pow(r - avgReturn, 2), 0) / returns.length
        : 0;
    const stdDev = Math.sqrt(variance);
    const sharpeRatio = stdDev > 0 ? avgReturn / stdDev : 0;

    return {
      totalTrades,
      winningTrades,
      losingTrades,
      totalPnl,
      maxDrawdown,
      sharpeRatio,
      winRate,
      avgWin,
      avgLoss,
      profitFactor,
      trades: this.trades,
    };
  }

  /**
   * Export results to CSV
   */
  exportToCSV(outputPath: string, result: BacktestResult): void {
    logger.info('Exporting results to CSV', { outputPath });

    const lines = [
      'Entry Time,Exit Time,Symbol,Side,Entry Price,Exit Price,Quantity,P&L',
    ];

    for (const trade of result.trades) {
      lines.push(
        [
          trade.entryTime.toISOString(),
          trade.exitTime.toISOString(),
          trade.symbol,
          trade.side,
          trade.entryPrice,
          trade.exitPrice,
          trade.quantity,
          trade.pnl,
        ].join(',')
      );
    }

    // Add summary
    lines.push('');
    lines.push('Summary');
    lines.push(`Total Trades,${result.totalTrades}`);
    lines.push(`Winning Trades,${result.winningTrades}`);
    lines.push(`Losing Trades,${result.losingTrades}`);
    lines.push(`Win Rate,${(result.winRate * 100).toFixed(2)}%`);
    lines.push(`Total P&L,${result.totalPnl.toFixed(2)}`);
    lines.push(`Average Win,${result.avgWin.toFixed(2)}`);
    lines.push(`Average Loss,${result.avgLoss.toFixed(2)}`);
    lines.push(`Profit Factor,${result.profitFactor.toFixed(2)}`);
    lines.push(`Max Drawdown,${(result.maxDrawdown * 100).toFixed(2)}%`);
    lines.push(`Sharpe Ratio,${result.sharpeRatio.toFixed(2)}`);

    fs.writeFileSync(outputPath, lines.join('\n'));

    logger.info('Results exported successfully');
  }
}

export default NodeBacktester;
