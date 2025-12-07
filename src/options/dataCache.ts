import { config } from '../config';
import { logger } from '../utils/logger';
import {
  OptionsChain,
  OptionChainEntry,
  OptionInstrument,
  Instrument,
} from '../types';

/**
 * Options Chain Data Cache
 * Features:
 * - Intelligent TTL based on strike distance from ATM
 * - Automatic refresh for near-expiry options
 * - Strike selection helpers
 * - Memory-efficient storage
 */

interface CacheEntry<T> {
  data: T;
  cachedAt: number;
  ttl: number;
}

export class OptionsDataCache {
  private chainCache: Map<string, CacheEntry<OptionsChain>> = new Map();
  private instrumentCache: Map<number, CacheEntry<Instrument>> = new Map();
  private ttlAtm: number;
  private ttlNear: number;
  private ttlFar: number;

  constructor(ttlAtm?: number, ttlNear?: number, ttlFar?: number) {
    this.ttlAtm = (ttlAtm || config.cache.ttlAtm) * 1000; // Convert to ms
    this.ttlNear = (ttlNear || config.cache.ttlNear) * 1000;
    this.ttlFar = (ttlFar || config.cache.ttlFar) * 1000;

    logger.info('OptionsDataCache initialized', {
      ttlAtm: this.ttlAtm / 1000,
      ttlNear: this.ttlNear / 1000,
      ttlFar: this.ttlFar / 1000,
    });
  }

  /**
   * Calculate appropriate TTL based on strike distance from spot
   */
  private calculateTTL(strike: number, spotPrice: number): number {
    const percentDiff = Math.abs((strike - spotPrice) / spotPrice) * 100;

    if (percentDiff < 2) {
      // Within 2% of ATM - short TTL
      return this.ttlAtm;
    } else if (percentDiff < 5) {
      // Within 5% of ATM - medium TTL
      return this.ttlNear;
    } else {
      // Far from ATM - long TTL
      return this.ttlFar;
    }
  }

  /**
   * Cache an options chain
   */
  cacheOptionsChain(underlying: string, expiry: Date, chain: OptionsChain): void {
    const key = this.getChainKey(underlying, expiry);

    this.chainCache.set(key, {
      data: chain,
      cachedAt: Date.now(),
      ttl: this.ttlNear, // Default TTL for entire chain
    });

    logger.debug('Options chain cached', {
      underlying,
      expiry: expiry.toISOString(),
      strikeCount: chain.strikes.size,
    });
  }

  /**
   * Get cached options chain
   */
  getOptionsChain(underlying: string, expiry: Date): OptionsChain | null {
    const key = this.getChainKey(underlying, expiry);
    const entry = this.chainCache.get(key);

    if (!entry) {
      return null;
    }

    const age = Date.now() - entry.cachedAt;

    if (age > entry.ttl) {
      // Cache expired
      this.chainCache.delete(key);
      logger.debug('Options chain cache expired', { underlying, expiry });
      return null;
    }

    logger.debug('Options chain cache hit', { underlying, expiry, age });
    return entry.data;
  }

  /**
   * Cache an individual option instrument
   */
  cacheOptionInstrument(
    instrument: OptionInstrument,
    spotPrice: number,
    lastPrice: number
  ): void {
    const ttl = this.calculateTTL(instrument.strike, spotPrice);

    this.instrumentCache.set(instrument.instrumentToken, {
      data: instrument,
      cachedAt: Date.now(),
      ttl,
    });

    logger.debug('Option instrument cached', {
      symbol: instrument.tradingSymbol,
      ttl: ttl / 1000,
    });
  }

  /**
   * Get cached instrument
   */
  getInstrument(instrumentToken: number): Instrument | null {
    const entry = this.instrumentCache.get(instrumentToken);

    if (!entry) {
      return null;
    }

    const age = Date.now() - entry.cachedAt;

    if (age > entry.ttl) {
      this.instrumentCache.delete(instrumentToken);
      return null;
    }

    return entry.data;
  }

  /**
   * Select closest strikes around a price
   */
  selectClosestStrikes(
    chain: OptionsChain,
    targetPrice: number,
    count: number = 5
  ): number[] {
    const strikes = Array.from(chain.strikes.keys()).sort((a, b) => a - b);

    if (strikes.length === 0) {
      return [];
    }

    // Find ATM strike (closest to target price)
    let atmIndex = 0;
    let minDiff = Math.abs(strikes[0] - targetPrice);

    for (let i = 1; i < strikes.length; i++) {
      const diff = Math.abs(strikes[i] - targetPrice);
      if (diff < minDiff) {
        minDiff = diff;
        atmIndex = i;
      }
    }

    // Select strikes around ATM
    const halfCount = Math.floor(count / 2);
    const startIndex = Math.max(0, atmIndex - halfCount);
    const endIndex = Math.min(strikes.length, atmIndex + halfCount + 1);

    return strikes.slice(startIndex, endIndex);
  }

  /**
   * Get ATM (at-the-money) strike
   */
  getATMStrike(chain: OptionsChain, spotPrice: number): number | null {
    const strikes = Array.from(chain.strikes.keys());

    if (strikes.length === 0) {
      return null;
    }

    // Find closest strike to spot price
    let atmStrike = strikes[0];
    let minDiff = Math.abs(strikes[0] - spotPrice);

    for (const strike of strikes) {
      const diff = Math.abs(strike - spotPrice);
      if (diff < minDiff) {
        minDiff = diff;
        atmStrike = strike;
      }
    }

    return atmStrike;
  }

  /**
   * Get ITM (in-the-money) strikes
   */
  getITMStrikes(
    chain: OptionsChain,
    spotPrice: number,
    optionType: 'CE' | 'PE',
    count: number = 5
  ): number[] {
    const strikes = Array.from(chain.strikes.keys()).sort((a, b) => a - b);

    if (optionType === 'CE') {
      // For calls, ITM strikes are below spot price
      return strikes.filter((s) => s < spotPrice).slice(-count);
    } else {
      // For puts, ITM strikes are above spot price
      return strikes.filter((s) => s > spotPrice).slice(0, count);
    }
  }

  /**
   * Get OTM (out-of-the-money) strikes
   */
  getOTMStrikes(
    chain: OptionsChain,
    spotPrice: number,
    optionType: 'CE' | 'PE',
    count: number = 5
  ): number[] {
    const strikes = Array.from(chain.strikes.keys()).sort((a, b) => a - b);

    if (optionType === 'CE') {
      // For calls, OTM strikes are above spot price
      return strikes.filter((s) => s > spotPrice).slice(0, count);
    } else {
      // For puts, OTM strikes are below spot price
      return strikes.filter((s) => s < spotPrice).slice(-count);
    }
  }

  /**
   * Build options chain from instruments list
   */
  buildOptionsChain(
    underlying: string,
    expiry: Date,
    instruments: OptionInstrument[],
    spotPrice: number
  ): OptionsChain {
    const strikes = new Map<
      number,
      { call?: OptionChainEntry; put?: OptionChainEntry }
    >();

    for (const instrument of instruments) {
      if (
        instrument.expiry.getTime() === expiry.getTime() &&
        instrument.underlying === underlying
      ) {
        const strike = instrument.strike;

        if (!strikes.has(strike)) {
          strikes.set(strike, {});
        }

        const strikeData = strikes.get(strike)!;

        const entry: OptionChainEntry = {
          instrument,
          lastPrice: instrument.lastPrice,
          cachedAt: new Date(),
        };

        if (instrument.instrumentType === 'CE') {
          strikeData.call = entry;
        } else {
          strikeData.put = entry;
        }
      }
    }

    const chain: OptionsChain = {
      underlying,
      spotPrice,
      expiry,
      strikes,
      updatedAt: new Date(),
    };

    // Cache the chain
    this.cacheOptionsChain(underlying, expiry, chain);

    return chain;
  }

  /**
   * Clear expired cache entries
   */
  clearExpired(): void {
    const now = Date.now();
    let expiredCount = 0;

    // Clear expired chains
    for (const [key, entry] of this.chainCache.entries()) {
      if (now - entry.cachedAt > entry.ttl) {
        this.chainCache.delete(key);
        expiredCount++;
      }
    }

    // Clear expired instruments
    for (const [token, entry] of this.instrumentCache.entries()) {
      if (now - entry.cachedAt > entry.ttl) {
        this.instrumentCache.delete(token);
        expiredCount++;
      }
    }

    if (expiredCount > 0) {
      logger.info('Cleared expired cache entries', { count: expiredCount });
    }
  }

  /**
   * Clear all cache
   */
  clearAll(): void {
    this.chainCache.clear();
    this.instrumentCache.clear();
    logger.info('All cache cleared');
  }

  /**
   * Get cache statistics
   */
  getStats(): {
    chainCount: number;
    instrumentCount: number;
    totalSize: number;
  } {
    return {
      chainCount: this.chainCache.size,
      instrumentCount: this.instrumentCache.size,
      totalSize: this.chainCache.size + this.instrumentCache.size,
    };
  }

  /**
   * Generate cache key for options chain
   */
  private getChainKey(underlying: string, expiry: Date): string {
    return `${underlying}_${expiry.toISOString().split('T')[0]}`;
  }
}

export default OptionsDataCache;
