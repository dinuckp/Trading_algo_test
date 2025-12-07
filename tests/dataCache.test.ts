import { OptionsDataCache } from '../src/options/dataCache';
import { OptionsChain, OptionInstrument } from '../src/types';

describe('OptionsDataCache', () => {
  let cache: OptionsDataCache;

  beforeEach(() => {
    cache = new OptionsDataCache(1, 2, 5); // Short TTLs for testing (seconds)
  });

  afterEach(() => {
    cache.clearAll();
  });

  const createMockInstrument = (
    strike: number,
    type: 'CE' | 'PE',
    price: number
  ): OptionInstrument => ({
    instrumentToken: Math.floor(Math.random() * 1000000),
    exchangeToken: 12345,
    tradingSymbol: `NIFTY24DEC${strike}${type}`,
    name: `NIFTY`,
    lastPrice: price,
    expiry: new Date('2024-12-26'),
    strike,
    tickSize: 0.05,
    lotSize: 25,
    instrumentType: type,
    segment: 'NFO-OPT',
    exchange: 'NFO',
    underlying: 'NIFTY',
  });

  const createMockChain = (spotPrice: number): OptionsChain => {
    const expiry = new Date('2024-12-26');
    const strikes = new Map();

    for (let strike = 19500; strike <= 20500; strike += 100) {
      strikes.set(strike, {
        call: {
          instrument: createMockInstrument(strike, 'CE', 100),
          lastPrice: 100,
          cachedAt: new Date(),
        },
        put: {
          instrument: createMockInstrument(strike, 'PE', 100),
          lastPrice: 100,
          cachedAt: new Date(),
        },
      });
    }

    return {
      underlying: 'NIFTY',
      spotPrice,
      expiry,
      strikes,
      updatedAt: new Date(),
    };
  };

  describe('cacheOptionsChain and getOptionsChain', () => {
    it('should cache and retrieve options chain', () => {
      const chain = createMockChain(20000);
      const expiry = new Date('2024-12-26');

      cache.cacheOptionsChain('NIFTY', expiry, chain);
      const retrieved = cache.getOptionsChain('NIFTY', expiry);

      expect(retrieved).not.toBeNull();
      expect(retrieved?.underlying).toBe('NIFTY');
      expect(retrieved?.spotPrice).toBe(20000);
      expect(retrieved?.strikes.size).toBe(11);
    });

    it('should return null for non-existent chain', () => {
      const expiry = new Date('2024-12-26');
      const retrieved = cache.getOptionsChain('BANKNIFTY', expiry);

      expect(retrieved).toBeNull();
    });

    it('should expire cache after TTL', async () => {
      const chain = createMockChain(20000);
      const expiry = new Date('2024-12-26');

      cache.cacheOptionsChain('NIFTY', expiry, chain);

      // Wait for cache to expire
      await new Promise((resolve) => setTimeout(resolve, 2500));

      const retrieved = cache.getOptionsChain('NIFTY', expiry);

      expect(retrieved).toBeNull();
    }, 10000);
  });

  describe('cacheOptionInstrument and getInstrument', () => {
    it('should cache and retrieve option instrument', () => {
      const instrument = createMockInstrument(20000, 'CE', 150);

      cache.cacheOptionInstrument(instrument, 20000, 150);
      const retrieved = cache.getInstrument(instrument.instrumentToken);

      expect(retrieved).not.toBeNull();
      expect(retrieved?.tradingSymbol).toBe(instrument.tradingSymbol);
    });

    it('should use shorter TTL for ATM options', () => {
      const atmInstrument = createMockInstrument(20000, 'CE', 150);

      // ATM option (within 2% of spot)
      cache.cacheOptionInstrument(atmInstrument, 20000, 150);

      // Should be cached
      expect(cache.getInstrument(atmInstrument.instrumentToken)).not.toBeNull();
    });

    it('should use longer TTL for far OTM options', () => {
      const otmInstrument = createMockInstrument(22000, 'CE', 10);

      // Far OTM option (more than 5% from spot)
      cache.cacheOptionInstrument(otmInstrument, 20000, 10);

      // Should be cached
      expect(cache.getInstrument(otmInstrument.instrumentToken)).not.toBeNull();
    });
  });

  describe('selectClosestStrikes', () => {
    it('should select strikes around target price', () => {
      const chain = createMockChain(20000);
      const strikes = cache.selectClosestStrikes(chain, 20000, 5);

      expect(strikes.length).toBeLessThanOrEqual(5);
      expect(strikes).toContain(20000); // Should include ATM
    });

    it('should handle target price between strikes', () => {
      const chain = createMockChain(20000);
      const strikes = cache.selectClosestStrikes(chain, 20050, 5);

      expect(strikes.length).toBeLessThanOrEqual(5);
      // Should include strikes around 20050
      expect(strikes.some((s) => Math.abs(s - 20050) <= 100)).toBe(true);
    });

    it('should return empty array for empty chain', () => {
      const emptyChain: OptionsChain = {
        underlying: 'NIFTY',
        spotPrice: 20000,
        expiry: new Date('2024-12-26'),
        strikes: new Map(),
        updatedAt: new Date(),
      };

      const strikes = cache.selectClosestStrikes(emptyChain, 20000, 5);

      expect(strikes).toEqual([]);
    });
  });

  describe('getATMStrike', () => {
    it('should find ATM strike', () => {
      const chain = createMockChain(20000);
      const atm = cache.getATMStrike(chain, 20000);

      expect(atm).toBe(20000);
    });

    it('should find closest strike when spot is between strikes', () => {
      const chain = createMockChain(20000);
      const atm = cache.getATMStrike(chain, 20050);

      expect(atm).toBeDefined();
      expect([20000, 20100]).toContain(atm!);
    });

    it('should return null for empty chain', () => {
      const emptyChain: OptionsChain = {
        underlying: 'NIFTY',
        spotPrice: 20000,
        expiry: new Date('2024-12-26'),
        strikes: new Map(),
        updatedAt: new Date(),
      };

      const atm = cache.getATMStrike(emptyChain, 20000);

      expect(atm).toBeNull();
    });
  });

  describe('getITMStrikes', () => {
    it('should get ITM strikes for call options', () => {
      const chain = createMockChain(20000);
      const itm = cache.getITMStrikes(chain, 20200, 'CE', 3);

      expect(itm.length).toBeLessThanOrEqual(3);
      // All strikes should be below spot price (ITM for calls)
      expect(itm.every((s) => s < 20200)).toBe(true);
    });

    it('should get ITM strikes for put options', () => {
      const chain = createMockChain(20000);
      const itm = cache.getITMStrikes(chain, 20000, 'PE', 3);

      expect(itm.length).toBeLessThanOrEqual(3);
      // All strikes should be above spot price (ITM for puts)
      expect(itm.every((s) => s > 20000)).toBe(true);
    });
  });

  describe('getOTMStrikes', () => {
    it('should get OTM strikes for call options', () => {
      const chain = createMockChain(20000);
      const otm = cache.getOTMStrikes(chain, 20000, 'CE', 3);

      expect(otm.length).toBeLessThanOrEqual(3);
      // All strikes should be above spot price (OTM for calls)
      expect(otm.every((s) => s > 20000)).toBe(true);
    });

    it('should get OTM strikes for put options', () => {
      const chain = createMockChain(20000);
      const otm = cache.getOTMStrikes(chain, 20200, 'PE', 3);

      expect(otm.length).toBeLessThanOrEqual(3);
      // All strikes should be below spot price (OTM for puts)
      expect(otm.every((s) => s < 20200)).toBe(true);
    });
  });

  describe('clearExpired', () => {
    it('should clear only expired entries', async () => {
      const chain = createMockChain(20000);
      const expiry = new Date('2024-12-26');

      cache.cacheOptionsChain('NIFTY', expiry, chain);

      // Wait for expiry
      await new Promise((resolve) => setTimeout(resolve, 2500));

      // Add a new entry
      const chain2 = createMockChain(20100);
      const expiry2 = new Date('2024-12-27');
      cache.cacheOptionsChain('BANKNIFTY', expiry2, chain2);

      // Clear expired
      cache.clearExpired();

      // Old entry should be gone
      expect(cache.getOptionsChain('NIFTY', expiry)).toBeNull();

      // New entry should still be there
      expect(cache.getOptionsChain('BANKNIFTY', expiry2)).not.toBeNull();
    }, 10000);
  });

  describe('clearAll', () => {
    it('should clear all cached data', () => {
      const chain = createMockChain(20000);
      const expiry = new Date('2024-12-26');

      cache.cacheOptionsChain('NIFTY', expiry, chain);

      cache.clearAll();

      expect(cache.getOptionsChain('NIFTY', expiry)).toBeNull();
      expect(cache.getStats().totalSize).toBe(0);
    });
  });

  describe('getStats', () => {
    it('should return cache statistics', () => {
      const stats = cache.getStats();

      expect(stats).toHaveProperty('chainCount');
      expect(stats).toHaveProperty('instrumentCount');
      expect(stats).toHaveProperty('totalSize');

      expect(stats.totalSize).toBe(stats.chainCount + stats.instrumentCount);
    });

    it('should reflect cached items', () => {
      const chain = createMockChain(20000);
      const expiry = new Date('2024-12-26');

      cache.cacheOptionsChain('NIFTY', expiry, chain);

      const stats = cache.getStats();

      expect(stats.chainCount).toBe(1);
      expect(stats.totalSize).toBeGreaterThan(0);
    });
  });
});
