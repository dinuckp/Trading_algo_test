#!/usr/bin/env node

import { Command } from 'commander';
import { KiteClient } from './kite/kiteClient';
import { Ticker } from './kite/ticker';
import { OrderThrottler } from './order/throttler';
import { RiskManager } from './order/riskManager';
import { OrderExecutor } from './order/orderExecutor';
import { OptionsDataCache } from './options/dataCache';
import { ExampleStrategy } from './strategy/exampleStrategy';
import { config, validateConfig } from './config';
import { logger } from './utils/logger';
import { TradeSignal } from './types';

/**
 * Kite Options Trading Application
 *
 * Main entry point for the application
 * Supports mock and live trading modes with comprehensive safety checks
 */

const program = new Command();

program
  .name('kite-options-trader')
  .description('Kite Options Algorithmic Trading Application')
  .version('1.0.0')
  .option('--mode <mode>', 'Trading mode: mock or live', 'mock')
  .option('--confirm-live', 'Confirm live trading (required for live mode)')
  .option('--request-token <token>', 'Request token from Kite login (for session generation)')
  .parse(process.argv);

const options = program.opts();

async function main(): Promise<void> {
  console.log('╔═══════════════════════════════════════════════════════════╗');
  console.log('║   Kite Options Algorithmic Trading Application           ║');
  console.log('╚═══════════════════════════════════════════════════════════╝');
  console.log();

  try {
    // Validate configuration
    validateConfig();

    // Determine trading mode
    const mockMode = options.mode === 'mock';
    const liveMode = options.mode === 'live';

    // CRITICAL SAFETY CHECKS
    if (liveMode && !options.confirmLive) {
      console.error('❌ ERROR: Live trading requires --confirm-live flag');
      console.error('   This is a safety measure to prevent accidental live trading');
      console.error('   Usage: npm run start -- --mode=live --confirm-live');
      process.exit(1);
    }

    if (liveMode && !config.trading.enableLiveOrders) {
      console.error('❌ ERROR: Live trading requires ENABLE_LIVE_ORDERS=true in .env');
      console.error('   Current setting: ENABLE_LIVE_ORDERS=false');
      console.error('   This is a safety measure to prevent accidental live trading');
      process.exit(1);
    }

    // Display mode
    if (mockMode) {
      console.log('📝 MODE: MOCK (Simulation)');
      console.log('   Orders will be simulated only. No real trades will be placed.');
      logger.info('Application started in MOCK mode');
    } else {
      console.log('🔴 MODE: LIVE (Real Trading)');
      console.log('   ⚠️  WARNING: Real orders will be placed!');
      console.log('   ⚠️  You can lose real money. Use at your own risk.');
      logger.warn('Application started in LIVE mode');

      // Additional confirmation
      console.log();
      console.log('Press Ctrl+C within 5 seconds to cancel...');
      await new Promise((resolve) => setTimeout(resolve, 5000));
      console.log('Proceeding with live trading...');
    }

    console.log();

    // Initialize Kite client
    logger.info('Initializing Kite client');
    const kiteClient = new KiteClient();

    // Initialize session
    const sessionResult = await kiteClient.init();

    if (!sessionResult.loggedIn) {
      if (options.requestToken) {
        // Generate session using provided request token
        console.log('Generating session with request token...');
        await kiteClient.generateSession(options.requestToken);
        console.log('✓ Session generated successfully');
      } else {
        // Need to login
        console.log();
        console.log('═══════════════════════════════════════════════════════════');
        console.log('LOGIN REQUIRED');
        console.log('═══════════════════════════════════════════════════════════');
        console.log();
        console.log('Please complete the following steps:');
        console.log();
        console.log('1. Open this URL in your browser:');
        console.log(`   ${sessionResult.loginUrl}`);
        console.log();
        console.log('2. Login with your Kite credentials');
        console.log();
        console.log('3. After login, you will be redirected to a URL like:');
        console.log('   http://127.0.0.1/?request_token=XXXXXX&action=login&status=success');
        console.log();
        console.log('4. Copy the request_token from the URL and run:');
        console.log('   npm run start -- --request-token=XXXXXX');
        console.log();
        console.log('═══════════════════════════════════════════════════════════');
        process.exit(0);
      }
    } else {
      console.log('✓ Session initialized successfully');
    }

    // Get user profile
    const profile = await kiteClient.getProfile();
    console.log(`✓ Logged in as: ${profile.user_name} (${profile.user_id})`);
    console.log();

    // Initialize components
    logger.info('Initializing trading components');

    const throttler = new OrderThrottler();
    const riskManager = new RiskManager();
    const orderExecutor = new OrderExecutor(
      kiteClient,
      throttler,
      riskManager,
      { mockMode }
    );
    const dataCache = new OptionsDataCache();

    console.log('✓ Trading components initialized');
    console.log();

    // Display configuration
    console.log('Configuration:');
    console.log(`  Throttle: ${config.throttle.ordersPerSecond}/sec, ${config.throttle.ordersPerMinute}/min`);
    console.log(`  Max Exposure: ₹${config.risk.maxTotalExposure.toLocaleString()}`);
    console.log(`  Max Risk/Trade: ₹${config.risk.maxRiskPerTrade.toLocaleString()}`);
    console.log();

    // Initialize WebSocket ticker
    const accessToken = kiteClient.getAccessToken();
    if (!accessToken) {
      throw new Error('No access token available');
    }

    const ticker = new Ticker({
      apiKey: config.kite.apiKey,
      accessToken,
    });

    // Initialize strategy
    logger.info('Initializing strategy');

    const strategyConfig = {
      underlying: 'NIFTY',
      underlyingToken: 256265, // NIFTY 50 index token
      priceThreshold: 50, // 50 points movement
      timeWindowSeconds: 300, // 5 minutes
      minDelta: 0.3,
      targetProfitPercent: 20,
      stopLossPercent: 10,
      riskFreeRate: 0.065, // 6.5% annual
      volatility: 0.15, // 15% assumed volatility
    };

    const strategy = new ExampleStrategy(strategyConfig, ticker, dataCache);

    console.log('✓ Strategy initialized');
    console.log(`  Underlying: ${strategyConfig.underlying}`);
    console.log(`  Price Threshold: ${strategyConfig.priceThreshold} pts in ${strategyConfig.timeWindowSeconds}s`);
    console.log();

    // Listen for trade signals
    strategy.on('signal', async (signal: TradeSignal) => {
      logger.info('Trade signal received', signal);

      console.log();
      console.log('═══════════════════════════════════════════════════════════');
      console.log('TRADE SIGNAL');
      console.log('═══════════════════════════════════════════════════════════');
      console.log(`Action:     ${signal.action}`);
      console.log(`Symbol:     ${signal.symbol}`);
      console.log(`Quantity:   ${signal.quantity}`);
      console.log(`Reason:     ${signal.reason}`);
      console.log(`Confidence: ${(signal.confidence * 100).toFixed(1)}%`);
      console.log('═══════════════════════════════════════════════════════════');
      console.log();

      // In a real implementation, you would:
      // 1. Validate the signal
      // 2. Get current option price
      // 3. Calculate Greeks
      // 4. Execute order through orderExecutor
      // For this example, we'll just log it
      logger.info('Signal processing not fully implemented in example');
    });

    // Connect ticker and start strategy
    console.log('Connecting to WebSocket...');
    ticker.connect();

    ticker.on('connect', () => {
      console.log('✓ WebSocket connected');
      console.log();
      console.log('Starting strategy...');
      strategy.start().catch((error) => {
        logger.error('Strategy failed', { error });
      });
      console.log('✓ Strategy started');
      console.log();
      console.log('Application is now running. Press Ctrl+C to exit.');
      console.log();
    });

    ticker.on('disconnect', (error) => {
      logger.warn('WebSocket disconnected', { error });
      console.log('⚠️  WebSocket disconnected. Reconnecting...');
    });

    ticker.on('error', (error) => {
      logger.error('WebSocket error', { error });
      console.error('❌ WebSocket error:', error.message);
    });

    // Handle graceful shutdown
    const shutdown = async (): Promise<void> => {
      console.log();
      console.log('Shutting down...');

      strategy.stop();
      ticker.disconnect();

      console.log('✓ Application stopped');
      process.exit(0);
    };

    process.on('SIGINT', shutdown);
    process.on('SIGTERM', shutdown);
  } catch (error) {
    logger.error('Application error', { error });
    console.error();
    console.error('❌ Error:', error instanceof Error ? error.message : error);
    process.exit(1);
  }
}

main().catch((error) => {
  logger.error('Unhandled error', { error });
  console.error('Unhandled error:', error);
  process.exit(1);
});
