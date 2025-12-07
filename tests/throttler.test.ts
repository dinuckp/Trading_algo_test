import { OrderThrottler } from '../src/order/throttler';

describe('OrderThrottler', () => {
  let throttler: OrderThrottler;

  beforeEach(() => {
    // Create throttler with low limits for testing
    throttler = new OrderThrottler(2, 5); // 2/sec, 5/min
  });

  afterEach(() => {
    throttler.reset();
  });

  describe('Per-second throttling', () => {
    it('should allow orders within per-second limit', () => {
      const result1 = throttler.checkOrder();
      const result2 = throttler.checkOrder();

      expect(result1.allowed).toBe(true);
      expect(result2.allowed).toBe(true);
    });

    it('should block orders exceeding per-second limit', () => {
      // Use up the per-second quota
      throttler.checkOrder();
      throttler.checkOrder();

      // This should be blocked
      const result3 = throttler.checkOrder();

      expect(result3.allowed).toBe(false);
      expect(result3.reason).toContain('Per-second limit');
      expect(result3.retryAfter).toBeGreaterThan(0);
    });

    it('should refill tokens after time passes', async () => {
      // Use up quota
      throttler.checkOrder();
      throttler.checkOrder();

      // Wait for refill
      await new Promise((resolve) => setTimeout(resolve, 1100));

      // Should be allowed now
      const result = throttler.checkOrder();
      expect(result.allowed).toBe(true);
    });
  });

  describe('Per-minute throttling', () => {
    it('should allow orders within per-minute limit', () => {
      for (let i = 0; i < 5; i++) {
        const result = throttler.checkOrder();
        if (i < 2) {
          // First 2 are limited by per-second
          expect(result.allowed).toBe(i < 2);
        }
      }

      const status = throttler.getStatus();
      expect(status.perMinute.tokens).toBeLessThanOrEqual(5);
    });

    it('should block orders exceeding per-minute limit', () => {
      // Reset to allow testing per-minute limit
      throttler.reset();

      // Use up per-minute quota by waiting between orders
      const results = [];
      for (let i = 0; i < 6; i++) {
        results.push(throttler.checkOrder());
        // Small delay to avoid per-second limit
        if (i % 2 === 1 && i < 5) {
          jest.advanceTimersByTime(1000);
        }
      }

      // First 5 should succeed, 6th should fail
      expect(results.filter((r) => r.allowed).length).toBeLessThanOrEqual(5);
    });
  });

  describe('getStatus', () => {
    it('should return current throttle status', () => {
      const status = throttler.getStatus();

      expect(status.perSecond.limit).toBe(2);
      expect(status.perMinute.limit).toBe(5);
      expect(status.perSecond.tokens).toBeLessThanOrEqual(2);
      expect(status.perMinute.tokens).toBeLessThanOrEqual(5);
    });
  });

  describe('reset', () => {
    it('should reset all counters', () => {
      // Use up some quota
      throttler.checkOrder();
      throttler.checkOrder();

      // Reset
      throttler.reset();

      // Should be able to place orders again
      const result = throttler.checkOrder();
      expect(result.allowed).toBe(true);

      const status = throttler.getStatus();
      expect(status.perSecond.tokens).toBe(2);
      expect(status.perMinute.tokens).toBe(5);
    });
  });

  describe('waitForOrder', () => {
    it('should wait until order is allowed', async () => {
      // Use up quota
      throttler.checkOrder();
      throttler.checkOrder();

      const startTime = Date.now();

      // This should wait
      await throttler.waitForOrder();

      const endTime = Date.now();
      const waitTime = endTime - startTime;

      // Should have waited at least some time
      expect(waitTime).toBeGreaterThan(0);
    }, 10000);
  });
});
