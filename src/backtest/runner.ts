#!/usr/bin/env node

import { Command } from 'commander';
import path from 'path';
import fs from 'fs';
import { NodeBacktester } from './nodeBacktester';
import { logger } from '../utils/logger';
import { TradeSignal } from '../types';
import { config } from '../config';

/**
 * Backtest Runner CLI
 *
 * Executes backtests using historical data and strategy signals
 */

const program = new Command();

program
  .name('backtest')
  .description('Run backtests on historical options data')
  .requiredOption('--data <file>', 'Path to historical data CSV file')
  .option('--signals <file>', 'Path to signals JSON file (optional for testing)')
  .option('--strategy <name>', 'Strategy to use (default: example)', 'example')
  .option('--output <file>', 'Output file for results (default: auto-generated)')
  .option('--initial-cash <amount>', 'Initial cash', '100000')
  .option('--commission <amount>', 'Commission per trade', '20')
  .option('--slippage <percent>', 'Slippage percentage', '0.001')
  .parse(process.argv);

const options = program.opts();

async function main(): Promise<void> {
  logger.info('Starting backtest runner', {
    dataFile: options.data,
    signalsFile: options.signals,
    strategy: options.strategy,
  });

  try {
    // Validate data file
    if (!fs.existsSync(options.data)) {
      throw new Error(`Data file not found: ${options.data}`);
    }

    // Initialize backtester
    const backtester = new NodeBacktester({
      initialCash: parseFloat(options.initialCash),
      commission: parseFloat(options.commission),
      slippage: parseFloat(options.slippage),
    });

    // Load historical data
    const ticks = backtester.loadDataFromCSV(options.data);

    // Load or generate signals
    let signals: TradeSignal[] = [];

    if (options.signals) {
      // Load signals from file
      if (!fs.existsSync(options.signals)) {
        throw new Error(`Signals file not found: ${options.signals}`);
      }

      const signalsContent = fs.readFileSync(options.signals, 'utf-8');
      signals = JSON.parse(signalsContent);

      logger.info('Signals loaded from file', { count: signals.length });
    } else {
      // Generate signals using strategy
      logger.info('Generating signals using strategy', {
        strategy: options.strategy,
      });

      // In a real implementation, you would:
      // 1. Load the strategy module
      // 2. Feed historical ticks to the strategy
      // 3. Collect generated signals
      // For now, we'll use empty signals array
      logger.warn('Strategy-based signal generation not yet implemented');
      logger.warn('Please provide signals file using --signals option');
      throw new Error('No signals provided');
    }

    // Run backtest
    const result = backtester.runBacktest(ticks, signals);

    // Print results
    console.log('\n' + '='.repeat(60));
    console.log('BACKTEST RESULTS');
    console.log('='.repeat(60));
    console.log(`Total Trades:      ${result.totalTrades}`);
    console.log(`Winning Trades:    ${result.winningTrades}`);
    console.log(`Losing Trades:     ${result.losingTrades}`);
    console.log(`Win Rate:          ${(result.winRate * 100).toFixed(2)}%`);
    console.log(`Total P&L:         ₹${result.totalPnl.toFixed(2)}`);
    console.log(`Average Win:       ₹${result.avgWin.toFixed(2)}`);
    console.log(`Average Loss:      ₹${result.avgLoss.toFixed(2)}`);
    console.log(`Profit Factor:     ${result.profitFactor.toFixed(2)}`);
    console.log(`Max Drawdown:      ${(result.maxDrawdown * 100).toFixed(2)}%`);
    console.log(`Sharpe Ratio:      ${result.sharpeRatio.toFixed(2)}`);
    console.log('='.repeat(60) + '\n');

    // Export to CSV
    const outputFile =
      options.output ||
      path.join(
        config.backtest.outputDir,
        `backtest_${Date.now()}.csv`
      );

    // Ensure output directory exists
    const outputDir = path.dirname(outputFile);
    if (!fs.existsSync(outputDir)) {
      fs.mkdirSync(outputDir, { recursive: true });
    }

    backtester.exportToCSV(outputFile, result);

    console.log(`Results exported to: ${outputFile}`);
    logger.info('Backtest completed successfully');
  } catch (error) {
    logger.error('Backtest failed', { error });
    console.error('Error:', error instanceof Error ? error.message : error);
    process.exit(1);
  }
}

main().catch((error) => {
  logger.error('Unhandled error', { error });
  process.exit(1);
});
