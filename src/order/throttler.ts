import { config } from '../config';
import { logger } from '../utils/logger';
import { ThrottleResult } from '../types';

/**
 * Token Bucket Rate Limiter
 * Enforces both per-second and per-minute order limits
 * Prevents overwhelming the broker's API and triggering rate limit blocks
 */

interface BucketConfig {
  capacity: number; // Max tokens
  refillRate: number; // Tokens per millisecond
  refillInterval: number; // Milliseconds between refills
}

class TokenBucket {
  private tokens: number;
  private lastRefill: number;
  private readonly capacity: number;
  private readonly refillRate: number;
  private readonly refillInterval: number;

  constructor(config: BucketConfig) {
    this.capacity = config.capacity;
    this.refillRate = config.refillRate;
    this.refillInterval = config.refillInterval;
    this.tokens = this.capacity;
    this.lastRefill = Date.now();
  }

  /**
   * Refill tokens based on time elapsed
   */
  private refill(): void {
    const now = Date.now();
    const elapsed = now - this.lastRefill;

    if (elapsed >= this.refillInterval) {
      const tokensToAdd =
        Math.floor(elapsed / this.refillInterval) * this.refillRate;
      this.tokens = Math.min(this.capacity, this.tokens + tokensToAdd);
      this.lastRefill = now;
    }
  }

  /**
   * Try to consume tokens
   * Returns true if successful, false if insufficient tokens
   */
  consume(count: number = 1): boolean {
    this.refill();

    if (this.tokens >= count) {
      this.tokens -= count;
      return true;
    }

    return false;
  }

  /**
   * Get time until next token is available (in milliseconds)
   */
  getRetryAfter(): number {
    this.refill();

    if (this.tokens >= 1) {
      return 0;
    }

    // Calculate time until next refill
    const timeSinceRefill = Date.now() - this.lastRefill;
    const timeUntilRefill = this.refillInterval - timeSinceRefill;

    return Math.max(0, timeUntilRefill);
  }

  /**
   * Get current token count
   */
  getTokens(): number {
    this.refill();
    return this.tokens;
  }

  /**
   * Reset the bucket
   */
  reset(): void {
    this.tokens = this.capacity;
    this.lastRefill = Date.now();
  }
}

export class OrderThrottler {
  private perSecondBucket: TokenBucket;
  private perMinuteBucket: TokenBucket;
  private ordersThisSecond = 0;
  private ordersThisMinute = 0;
  private readonly maxOrdersPerSecond: number;
  private readonly maxOrdersPerMinute: number;

  constructor(
    maxOrdersPerSecond?: number,
    maxOrdersPerMinute?: number
  ) {
    this.maxOrdersPerSecond =
      maxOrdersPerSecond || config.throttle.ordersPerSecond;
    this.maxOrdersPerMinute =
      maxOrdersPerMinute || config.throttle.ordersPerMinute;

    // Per-second bucket: refills every second
    this.perSecondBucket = new TokenBucket({
      capacity: this.maxOrdersPerSecond,
      refillRate: this.maxOrdersPerSecond,
      refillInterval: 1000, // 1 second
    });

    // Per-minute bucket: refills every minute
    this.perMinuteBucket = new TokenBucket({
      capacity: this.maxOrdersPerMinute,
      refillRate: this.maxOrdersPerMinute,
      refillInterval: 60000, // 1 minute
    });

    logger.info('OrderThrottler initialized', {
      maxOrdersPerSecond: this.maxOrdersPerSecond,
      maxOrdersPerMinute: this.maxOrdersPerMinute,
    });
  }

  /**
   * Check if an order can be placed
   * Returns result indicating whether order is allowed and retry time if not
   */
  checkOrder(): ThrottleResult {
    const perSecondAllowed = this.perSecondBucket.consume(1);
    const perMinuteAllowed = this.perMinuteBucket.consume(1);

    if (!perSecondAllowed) {
      const retryAfter = this.perSecondBucket.getRetryAfter();
      logger.warn('Order throttled: per-second limit exceeded', {
        retryAfter,
        limit: this.maxOrdersPerSecond,
      });

      // Restore the minute bucket token since we're not placing order
      this.perMinuteBucket.consume(-1);

      return {
        allowed: false,
        retryAfter,
        reason: `Per-second limit (${this.maxOrdersPerSecond}) exceeded`,
      };
    }

    if (!perMinuteAllowed) {
      const retryAfter = this.perMinuteBucket.getRetryAfter();
      logger.warn('Order throttled: per-minute limit exceeded', {
        retryAfter,
        limit: this.maxOrdersPerMinute,
      });

      // Restore the second bucket token since we're not placing order
      this.perSecondBucket.consume(-1);

      return {
        allowed: false,
        retryAfter,
        reason: `Per-minute limit (${this.maxOrdersPerMinute}) exceeded`,
      };
    }

    this.ordersThisSecond++;
    this.ordersThisMinute++;

    logger.debug('Order throttle check passed', {
      ordersThisSecond: this.ordersThisSecond,
      ordersThisMinute: this.ordersThisMinute,
    });

    return {
      allowed: true,
    };
  }

  /**
   * Wait until an order can be placed
   * Returns promise that resolves when throttle allows the order
   */
  async waitForOrder(): Promise<void> {
    let result = this.checkOrder();

    while (!result.allowed) {
      const waitTime = result.retryAfter || 1000;
      logger.info('Waiting for throttle', { waitTime });

      await new Promise((resolve) => setTimeout(resolve, waitTime));

      result = this.checkOrder();
    }
  }

  /**
   * Get current throttle status
   */
  getStatus(): {
    perSecond: { tokens: number; limit: number };
    perMinute: { tokens: number; limit: number };
  } {
    return {
      perSecond: {
        tokens: Math.floor(this.perSecondBucket.getTokens()),
        limit: this.maxOrdersPerSecond,
      },
      perMinute: {
        tokens: Math.floor(this.perMinuteBucket.getTokens()),
        limit: this.maxOrdersPerMinute,
      },
    };
  }

  /**
   * Reset throttle counters (useful for testing)
   */
  reset(): void {
    this.perSecondBucket.reset();
    this.perMinuteBucket.reset();
    this.ordersThisSecond = 0;
    this.ordersThisMinute = 0;
    logger.info('Throttler reset');
  }
}

export default OrderThrottler;
