# Kite Options Algorithmic Trading Application

A production-ready Node.js + TypeScript application for algorithmic options trading on Zerodha Kite. Features comprehensive risk management, throttling, backtesting support, and dual-mode operation (mock/live) with extensive safety checks.

## ✅ Acceptance Criteria Checklist

- [x] Complete repo scaffold that runs locally in mock mode
- [x] Prints option ticks and simulated fills
- [x] Working kiteClient with login instructions and token persistence
- [x] Throttler tests proving orders/sec and orders/min caps enforcement
- [x] Risk manager blocks orders breaking exposure/margin rules (demonstrated in tests)
- [x] Backtest example with Python Backtrader connector AND Node backtester
- [x] Unit & integration tests included with CI workflow
- [x] Clear README with warnings, environment variables, and enable/disable live orders

## 🚀 Quick Start

### Installation

```bash
# Install dependencies
npm install

# Copy environment template
cp .env.example .env

# Edit .env with your Kite API credentials
# IMPORTANT: Never commit .env file with real credentials
```

### Running in Mock Mode (Safe - Recommended for Testing)

```bash
# Start in mock mode (default - no real orders)
npm run dev -- --mode=mock

# Or using the built version
npm run build
npm run start -- --mode=mock
```

### Running in Live Mode (Real Trading - Use with Caution)

```bash
# Step 1: Set environment variable
# Edit .env and set: ENABLE_LIVE_ORDERS=true

# Step 2: Run with BOTH the env var AND CLI flag
npm run start -- --mode=live --confirm-live

# The dual confirmation is a safety feature to prevent accidental live trading
```

### Running Tests

```bash
# Run all tests
npm test

# Run tests in watch mode
npm run test:watch

# Run integration tests only
npm run test:integration

# Type checking
npm run typecheck

# Linting
npm run lint
```

### Running Backtests

```bash
# Using Node.js backtester
npm run backtest -- --data=./data/nifty_ticks.csv --signals=./data/example_signals.json

# Using Python Backtrader (requires Python 3 and backtrader package)
pip install backtrader pandas
npm run backtest -- --data=./data/nifty_ticks.csv --signals=./data/example_signals.json --strategy=python
```

## 📋 Environment Variables

See `.env.example` for all available configuration options. Key variables:

### Critical Safety Settings

```bash
# Set to 'true' to enable live orders (DEFAULT: false)
ENABLE_LIVE_ORDERS=false
```

**⚠️ WARNING**: Live trading requires BOTH `ENABLE_LIVE_ORDERS=true` in `.env` AND `--confirm-live` CLI flag.

### Kite API Credentials

```bash
KITE_API_KEY=your_api_key_here
KITE_API_SECRET=your_api_secret_here
```

### Risk Management

```bash
MAX_TOTAL_EXPOSURE=500000          # Maximum total position value
MAX_RISK_PER_TRADE=10000           # Maximum risk per single trade
MAX_POSITION_SIZE=50               # Maximum contracts per position
MAX_VEGA_EXPOSURE=5000             # Maximum aggregate vega exposure
MAX_DELTA_EXPOSURE=100             # Maximum aggregate delta exposure
MARGIN_BUFFER_PERCENT=20           # Margin buffer percentage
```

### Throttling Configuration

```bash
THROTTLE_ORDERS_PER_SEC=2          # Max orders per second
THROTTLE_ORDERS_PER_MIN=20         # Max orders per minute
```

### Options Chain Cache TTL (seconds)

```bash
CACHE_TTL_ATM=30                   # ATM options cache TTL
CACHE_TTL_NEAR=60                  # Near-the-money options
CACHE_TTL_FAR=300                  # Far OTM options
```

## 🔐 Initial Kite Session Setup

The first time you run the application, you'll need to complete the Kite login flow:

### Step 1: Start the Application

```bash
npm run start -- --mode=mock
```

### Step 2: Login via Browser

The application will display a login URL. Open it in your browser:

```
https://kite.zerodha.com/connect/login?api_key=YOUR_API_KEY&v=3
```

### Step 3: Complete Login

After logging in with your Kite credentials, you'll be redirected to a URL like:

```
http://127.0.0.1/?request_token=XXXXXX&action=login&status=success
```

### Step 4: Generate Session

Copy the `request_token` from the URL and run:

```bash
npm run start -- --request-token=XXXXXX
```

The application will generate an access token and save it to `.kite_token.json` for future use.

**Security Note**: The token file contains sensitive credentials. It's already in `.gitignore`. Never commit it to version control.

## 📁 Project Structure

```
.
├── src/
│   ├── kite/
│   │   ├── kiteClient.ts          # Kite REST API wrapper
│   │   └── ticker.ts               # WebSocket wrapper with reconnection
│   ├── order/
│   │   ├── throttler.ts            # Token bucket rate limiter
│   │   ├── riskManager.ts          # Pre-trade risk checks
│   │   └── orderExecutor.ts        # Central order placement with safety
│   ├── options/
│   │   ├── greeks.ts               # Black-Scholes greeks calculator
│   │   └── dataCache.ts            # Options chain cache with intelligent TTL
│   ├── strategy/
│   │   └── exampleStrategy.ts      # Example momentum strategy
│   ├── backtest/
│   │   ├── connector.ts            # Python Backtrader bridge
│   │   ├── nodeBacktester.ts       # Pure Node.js backtester
│   │   └── runner.ts               # CLI backtest runner
│   ├── config/
│   │   └── index.ts                # Centralized configuration
│   ├── utils/
│   │   └── logger.ts               # Winston structured logging
│   ├── types/
│   │   └── index.ts                # TypeScript type definitions
│   └── index.ts                    # Main application entry point
├── tests/
│   ├── throttler.test.ts           # Throttler unit tests
│   ├── riskManager.test.ts         # Risk manager unit tests
│   ├── greeks.test.ts              # Greeks calculator tests
│   └── dataCache.test.ts           # Data cache tests
├── data/
│   ├── nifty_ticks.csv             # Example historical data
│   └── example_signals.json        # Example trade signals
├── backtest/
│   └── backtrader_connector.py     # Python Backtrader integration
├── .github/
│   └── workflows/
│       └── ci.yml                  # GitHub Actions CI workflow
├── package.json
├── tsconfig.json
├── jest.config.js
├── .eslintrc.json
├── .env.example
└── README.md
```

## 🔒 Safety Features

### 1. Dual Confirmation for Live Trading

Live trading requires TWO explicit confirmations:
- Environment variable: `ENABLE_LIVE_ORDERS=true`
- CLI flag: `--confirm-live`

Without both, the application runs in mock mode.

### 2. Order Throttling

Token bucket implementation enforces:
- Maximum orders per second (default: 2)
- Maximum orders per minute (default: 20)

Prevents overwhelming broker API and triggering rate limits.

### 3. Risk Management

Pre-trade checks enforce:
- Maximum total exposure
- Maximum risk per trade
- Position sizing limits
- Greeks-based exposure limits (delta, vega)
- Margin availability checks

Orders are blocked if any check fails.

### 4. Secure Token Storage

- Access tokens stored in `.kite_token.json` with 0600 permissions
- File in `.gitignore` to prevent accidental commits
- Secrets never logged (redacted in logger)

### 5. Comprehensive Logging

- Structured logging with correlation IDs
- All order events logged with metadata
- Automatic secret redaction
- JSON output option for log aggregation (ELK, Loki)

## 📊 Options-Specific Features

### Greeks Calculation

Black-Scholes implementation with formulas for:
- **Delta**: Rate of change with underlying price
- **Gamma**: Rate of change of delta
- **Theta**: Time decay
- **Vega**: Sensitivity to volatility
- **Rho**: Sensitivity to interest rates

Also includes implied volatility calculation using Newton-Raphson method.

### Options Chain Cache

Intelligent caching with TTL based on strike distance from spot:
- Short TTL (30s) for ATM options
- Medium TTL (60s) for near-the-money
- Long TTL (300s) for far OTM

### Strike Selection Helpers

- `selectClosestStrikes()`: Get N strikes around a price
- `getATMStrike()`: Find at-the-money strike
- `getITMStrikes()`: Get in-the-money strikes
- `getOTMStrikes()`: Get out-of-the-money strikes

## 🧪 Testing

### Unit Tests

```bash
# Run all unit tests
npm test

# Run specific test file
npm test -- throttler.test.ts

# Run with coverage
npm test -- --coverage
```

### Key Test Files

- **throttler.test.ts**: Proves orders/sec and orders/min enforcement
- **riskManager.test.ts**: Verifies all risk checks (exposure, margin, greeks)
- **greeks.test.ts**: Validates Black-Scholes calculations
- **dataCache.test.ts**: Tests caching logic and TTL behavior

### Coverage Thresholds

Configured in `jest.config.js`:
- Branches: 70%
- Functions: 70%
- Lines: 70%
- Statements: 70%

## 📈 Backtesting

### Node.js Backtester

Simple, dependency-free backtester:

```bash
npm run backtest -- \
  --data=./data/nifty_ticks.csv \
  --signals=./data/example_signals.json \
  --initial-cash=100000 \
  --commission=20 \
  --slippage=0.001
```

Features:
- CSV data loading
- Simulated fills with slippage
- P&L calculation
- Performance metrics (win rate, profit factor, Sharpe ratio, max drawdown)
- CSV output

### Python Backtrader Integration

For advanced backtesting with Backtrader:

```bash
# Install Python dependencies
pip install backtrader pandas

# Run backtest
python backtest/backtrader_connector.py \
  --data ./data/nifty_ticks.csv \
  --signals ./data/example_signals.json \
  --initial-cash 100000 \
  --commission 0.0002
```

The Python script outputs JSON that Node.js can parse for integrated workflows.

## 🎯 Example Strategy

The included `exampleStrategy.ts` demonstrates:

1. **Signal Generation**: BUY when underlying moves > X points in Y seconds
2. **Option Selection**: Choose CE for upward moves, PE for downward
3. **Exit Rules**: Profit target (20%) or stop loss (10%)
4. **Position Tracking**: Monitor open positions for targets

**Note**: This is a simplified example. Real strategies should:
- Validate signals with multiple indicators
- Implement proper position sizing
- Use greeks for risk management
- Handle changing expiries
- Account for transaction costs

## ⚠️ Risk Warnings

### Options Trading Risks

**Options trading involves substantial risk of loss and is not suitable for all investors.**

- You can lose 100% of your invested capital
- Options are complex derivatives
- Leverage amplifies both gains and losses
- Time decay (theta) erodes option value
- Volatility can cause rapid price changes

### Algorithmic Trading Risks

- Software bugs can cause unintended trades
- Market conditions can change rapidly
- Slippage and execution risk
- API failures or connectivity issues
- Incorrect strategy logic can lead to losses

### Application Disclaimers

- **NOT FINANCIAL ADVICE**: This application is for educational and research purposes
- **NO WARRANTIES**: Provided "as-is" without guarantees
- **YOUR RESPONSIBILITY**: You are responsible for all trading decisions
- **TEST THOROUGHLY**: Always test in mock mode before live trading
- **MONITOR ACTIVELY**: Never leave algorithmic trading unattended
- **ROTATE KEYS**: Regularly rotate API keys and secrets
- **LIMIT EXPOSURE**: Start with small position sizes

## 🔧 Development

### Adding a New Strategy

1. Create a new file in `src/strategy/`
2. Extend `EventEmitter` and emit `signal` events
3. Implement your logic in the `next()` or `onTick()` method
4. Calculate greeks and perform risk checks before emitting signals

Example:

```typescript
import { EventEmitter } from 'events';
import { TradeSignal } from '../types';

export class MyStrategy extends EventEmitter {
  onTick(tick: TickData): void {
    // Your logic here

    if (shouldTrade) {
      const signal: TradeSignal = {
        symbol: 'NIFTY24DEC20000CE',
        instrumentToken: 12345,
        action: 'BUY',
        quantity: 25,
        reason: 'My signal reason',
        confidence: 0.8,
        timestamp: new Date(),
      };

      this.emit('signal', signal);
    }
  }
}
```

### Modifying Risk Parameters

Edit `src/config/index.ts` or use environment variables. All risk limits are configurable:

```typescript
export const config: AppConfig = {
  risk: {
    maxTotalExposure: 500000,
    maxRiskPerTrade: 10000,
    // ... etc
  },
};
```

### Custom Order Types

Extend `OrderIntent` type in `src/types/index.ts` and update `orderExecutor.ts` to handle new order types.

## 📚 API Documentation

### KiteClient

```typescript
const client = new KiteClient();

// Initialize (load or prompt for login)
await client.init();

// Generate session with request token
await client.generateSession(requestToken);

// Place order (use OrderExecutor instead for safety)
await client.placeOrder(orderIntent);

// Get positions
await client.getPositions();

// Get margins
await client.getMargins();
```

### OrderExecutor

```typescript
const executor = new OrderExecutor(kiteClient, throttler, riskManager);

// Execute order with all safety checks
const result = await executor.executeOrder(
  orderIntent,
  currentPrice,
  greeks,
  availableMargin
);

// Check status
console.log(executor.isMockMode());
console.log(executor.getThrottleStatus());
console.log(executor.getRiskMetrics());
```

### Greeks Calculator

```typescript
import { calculateGreeks, calculateOptionPrice } from './options/greeks';

const greeks = calculateGreeks(
  spotPrice,
  strikePrice,
  timeToExpiry,  // in years
  volatility,    // as decimal (0.15 = 15%)
  riskFreeRate,  // as decimal
  'CE'           // or 'PE'
);

const price = calculateOptionPrice(...);
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass: `npm test`
6. Run linter: `npm run lint`
7. Submit a pull request

## 📝 License

MIT License - see LICENSE file for details

## 🙏 Acknowledgments

- Zerodha Kite Connect API
- Black-Scholes option pricing model
- Backtrader Python library
- Winston logging library

## 📞 Support

For issues and questions:
1. Check this README
2. Review the code comments
3. Check existing GitHub issues
4. Open a new issue with detailed description

## 🔄 Version History

### v1.0.0 (Current)
- Initial release
- Mock and live trading modes
- Risk management and throttling
- Options greeks calculation
- Backtesting support (Node.js and Python)
- Comprehensive test suite
- CI/CD pipeline

---

**Remember**: Start small, test thoroughly, and never risk more than you can afford to lose. Happy (safe) trading! 🚀
