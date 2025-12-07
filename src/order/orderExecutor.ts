import { KiteClient } from '../kite/kiteClient';
import { OrderThrottler } from './throttler';
import { RiskManager } from './riskManager';
import { config } from '../config';
import { logger, createChildLogger } from '../utils/logger';
import {
  OrderIntent,
  OrderResult,
  Greeks,
} from '../types';
import crypto from 'crypto';

/**
 * OrderExecutor - Central order placement with safety features
 * Features:
 * - Mock/Live mode switching with dual confirmation
 * - Throttling to respect rate limits
 * - Risk checks before order placement
 * - Retry logic with exponential backoff
 * - Comprehensive logging
 */

export interface OrderExecutorConfig {
  mockMode?: boolean;
  enableLiveOrders?: boolean;
  maxRetries?: number;
  retryBaseDelay?: number;
}

export class OrderExecutor {
  private kiteClient: KiteClient;
  private throttler: OrderThrottler;
  private riskManager: RiskManager;
  private mockMode: boolean;
  private enableLiveOrders: boolean;
  private maxRetries: number;
  private retryBaseDelay: number;
  private mockOrderIdCounter = 1;

  constructor(
    kiteClient: KiteClient,
    throttler: OrderThrottler,
    riskManager: RiskManager,
    customConfig?: OrderExecutorConfig
  ) {
    this.kiteClient = kiteClient;
    this.throttler = throttler;
    this.riskManager = riskManager;

    this.mockMode = customConfig?.mockMode ?? config.trading.mockMode;
    this.enableLiveOrders =
      customConfig?.enableLiveOrders ?? config.trading.enableLiveOrders;
    this.maxRetries = customConfig?.maxRetries ?? 3;
    this.retryBaseDelay = customConfig?.retryBaseDelay ?? 1000;

    // CRITICAL SAFETY CHECK
    if (!this.mockMode && !this.enableLiveOrders) {
      logger.error(
        'SAFETY: Live orders attempted without ENABLE_LIVE_ORDERS=true. Forcing mock mode.'
      );
      this.mockMode = true;
    }

    logger.info('OrderExecutor initialized', {
      mockMode: this.mockMode,
      enableLiveOrders: this.enableLiveOrders,
    });

    if (this.mockMode) {
      logger.warn('⚠️  MOCK MODE ENABLED - Orders will be simulated only');
    } else {
      logger.warn('🔴 LIVE MODE ENABLED - Real orders will be placed');
    }
  }

  /**
   * Execute an order with full safety checks
   */
  async executeOrder(
    orderIntent: OrderIntent,
    currentPrice: number,
    greeks?: Greeks,
    availableMargin?: number
  ): Promise<OrderResult> {
    const correlationId = this.generateCorrelationId();
    const childLogger = createChildLogger(correlationId);

    childLogger.info('Order execution requested', {
      symbol: orderIntent.symbol,
      transaction: orderIntent.transactionType,
      quantity: orderIntent.quantity,
      orderType: orderIntent.orderType,
    });

    try {
      // Step 1: Check throttle
      const throttleResult = this.throttler.checkOrder();
      if (!throttleResult.allowed) {
        childLogger.warn('Order rejected by throttler', {
          reason: throttleResult.reason,
          retryAfter: throttleResult.retryAfter,
        });

        return {
          success: false,
          error: throttleResult.reason,
          timestamp: new Date(),
          mock: this.mockMode,
        };
      }

      // Step 2: Risk checks
      const riskResult = this.riskManager.checkOrder(
        orderIntent,
        currentPrice,
        greeks,
        availableMargin
      );

      if (!riskResult.allowed) {
        childLogger.warn('Order rejected by risk manager', {
          reason: riskResult.reason,
          checks: riskResult.checks,
        });

        return {
          success: false,
          error: riskResult.reason,
          timestamp: new Date(),
          mock: this.mockMode,
        };
      }

      // Step 3: Place order (mock or live)
      let result: OrderResult;

      if (this.mockMode) {
        result = await this.placeMockOrder(orderIntent, correlationId);
      } else {
        result = await this.placeLiveOrder(orderIntent, correlationId);
      }

      // Step 4: Update exposure if successful
      if (result.success) {
        this.riskManager.updateExposure(
          orderIntent.symbol,
          orderIntent.quantity,
          currentPrice,
          orderIntent.transactionType,
          greeks
        );
      }

      return result;
    } catch (error) {
      childLogger.error('Order execution failed', { error });
      return {
        success: false,
        error: error instanceof Error ? error.message : 'Unknown error',
        timestamp: new Date(),
        mock: this.mockMode,
      };
    }
  }

  /**
   * Place a live order with retries
   */
  private async placeLiveOrder(
    orderIntent: OrderIntent,
    correlationId: string
  ): Promise<OrderResult> {
    const childLogger = createChildLogger(correlationId);

    // CRITICAL SAFETY CHECK
    if (!this.enableLiveOrders) {
      childLogger.error('SAFETY: Live orders not enabled. Set ENABLE_LIVE_ORDERS=true');
      throw new Error('Live orders not enabled');
    }

    childLogger.warn('🔴 Placing LIVE order');

    let lastError: Error | null = null;

    for (let attempt = 1; attempt <= this.maxRetries; attempt++) {
      try {
        const response = await this.kiteClient.placeOrder(orderIntent);

        childLogger.info('Live order placed successfully', {
          orderId: response.order_id,
          attempt,
        });

        return {
          success: true,
          orderId: response.order_id,
          message: 'Order placed successfully',
          timestamp: new Date(),
          mock: false,
        };
      } catch (error) {
        lastError = error instanceof Error ? error : new Error(String(error));

        childLogger.warn('Order placement failed', {
          attempt,
          error: lastError.message,
        });

        // Check if error is retryable
        if (!this.isRetryableError(lastError)) {
          childLogger.error('Non-retryable error encountered', {
            error: lastError.message,
          });
          break;
        }

        // Wait before retry with exponential backoff
        if (attempt < this.maxRetries) {
          const delay = this.retryBaseDelay * Math.pow(2, attempt - 1);
          childLogger.info('Retrying order placement', {
            attempt,
            delayMs: delay,
          });
          await this.sleep(delay);
        }
      }
    }

    return {
      success: false,
      error: lastError?.message || 'Order placement failed',
      timestamp: new Date(),
      mock: false,
    };
  }

  /**
   * Place a mock order (simulation)
   */
  private async placeMockOrder(
    orderIntent: OrderIntent,
    correlationId: string
  ): Promise<OrderResult> {
    const childLogger = createChildLogger(correlationId);

    childLogger.info('📝 Placing MOCK order (simulation)');

    // Simulate network delay
    await this.sleep(100 + Math.random() * 200);

    // Simulate 95% success rate
    const success = Math.random() > 0.05;

    if (success) {
      const mockOrderId = `MOCK-${Date.now()}-${this.mockOrderIdCounter++}`;

      childLogger.info('Mock order placed successfully', {
        orderId: mockOrderId,
      });

      return {
        success: true,
        orderId: mockOrderId,
        message: 'Mock order placed successfully',
        timestamp: new Date(),
        mock: true,
      };
    } else {
      childLogger.warn('Mock order failed (simulated failure)');

      return {
        success: false,
        error: 'Mock order failed (random simulation)',
        timestamp: new Date(),
        mock: true,
      };
    }
  }

  /**
   * Check if error is retryable
   */
  private isRetryableError(error: Error): boolean {
    const retryableMessages = [
      'network',
      'timeout',
      'econnreset',
      'econnrefused',
      'temporary',
      'try again',
    ];

    const errorMessage = error.message.toLowerCase();
    return retryableMessages.some((msg) => errorMessage.includes(msg));
  }

  /**
   * Generate correlation ID for tracking
   */
  private generateCorrelationId(): string {
    return crypto.randomBytes(4).toString('hex');
  }

  /**
   * Sleep utility
   */
  private sleep(ms: number): Promise<void> {
    return new Promise((resolve) => setTimeout(resolve, ms));
  }

  /**
   * Check if executor is in mock mode
   */
  isMockMode(): boolean {
    return this.mockMode;
  }

  /**
   * Get throttler status
   */
  getThrottleStatus(): ReturnType<OrderThrottler['getStatus']> {
    return this.throttler.getStatus();
  }

  /**
   * Get risk metrics
   */
  getRiskMetrics(): ReturnType<RiskManager['getRiskMetrics']> {
    return this.riskManager.getRiskMetrics();
  }
}

export default OrderExecutor;
