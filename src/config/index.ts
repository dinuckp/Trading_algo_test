import dotenv from 'dotenv';
import path from 'path';

// Load environment variables
dotenv.config();

/**
 * Application configuration
 * All configuration values loaded from environment variables with sensible defaults
 */

export interface AppConfig {
  kite: {
    apiKey: string;
    apiSecret: string;
    tokenPath: string;
  };
  trading: {
    enableLiveOrders: boolean;
    mockMode: boolean;
  };
  throttle: {
    ordersPerSecond: number;
    ordersPerMinute: number;
  };
  risk: {
    maxTotalExposure: number;
    maxRiskPerTrade: number;
    maxPositionSize: number;
    maxVegaExposure: number;
    maxDeltaExposure: number;
    marginBufferPercent: number;
  };
  cache: {
    ttlAtm: number;
    ttlNear: number;
    ttlFar: number;
  };
  websocket: {
    reconnectMaxDelay: number;
    reconnectMaxTries: number;
  };
  logging: {
    level: string;
    filePath: string;
    json: boolean;
  };
  backtest: {
    dataDir: string;
    outputDir: string;
    pythonPath: string;
    backtraderScriptPath: string;
  };
}

function getEnvVar(key: string, defaultValue: string): string {
  return process.env[key] || defaultValue;
}

function getEnvVarNumber(key: string, defaultValue: number): number {
  const value = process.env[key];
  return value ? parseFloat(value) : defaultValue;
}

function getEnvVarBoolean(key: string, defaultValue: boolean): boolean {
  const value = process.env[key];
  if (value === undefined) return defaultValue;
  return value.toLowerCase() === 'true';
}

export const config: AppConfig = {
  kite: {
    apiKey: getEnvVar('KITE_API_KEY', ''),
    apiSecret: getEnvVar('KITE_API_SECRET', ''),
    tokenPath: getEnvVar('KITE_TOKEN_PATH', '.kite_token.json'),
  },
  trading: {
    enableLiveOrders: getEnvVarBoolean('ENABLE_LIVE_ORDERS', false),
    mockMode: !getEnvVarBoolean('ENABLE_LIVE_ORDERS', false),
  },
  throttle: {
    ordersPerSecond: getEnvVarNumber('THROTTLE_ORDERS_PER_SEC', 2),
    ordersPerMinute: getEnvVarNumber('THROTTLE_ORDERS_PER_MIN', 20),
  },
  risk: {
    maxTotalExposure: getEnvVarNumber('MAX_TOTAL_EXPOSURE', 500000),
    maxRiskPerTrade: getEnvVarNumber('MAX_RISK_PER_TRADE', 10000),
    maxPositionSize: getEnvVarNumber('MAX_POSITION_SIZE', 50),
    maxVegaExposure: getEnvVarNumber('MAX_VEGA_EXPOSURE', 5000),
    maxDeltaExposure: getEnvVarNumber('MAX_DELTA_EXPOSURE', 100),
    marginBufferPercent: getEnvVarNumber('MARGIN_BUFFER_PERCENT', 20),
  },
  cache: {
    ttlAtm: getEnvVarNumber('CACHE_TTL_ATM', 30),
    ttlNear: getEnvVarNumber('CACHE_TTL_NEAR', 60),
    ttlFar: getEnvVarNumber('CACHE_TTL_FAR', 300),
  },
  websocket: {
    reconnectMaxDelay: getEnvVarNumber('WS_RECONNECT_MAX_DELAY', 60000),
    reconnectMaxTries: getEnvVarNumber('WS_RECONNECT_MAX_TRIES', 10),
  },
  logging: {
    level: getEnvVar('LOG_LEVEL', 'info'),
    filePath: getEnvVar('LOG_FILE_PATH', './logs/app.log'),
    json: getEnvVarBoolean('LOG_JSON', true),
  },
  backtest: {
    dataDir: getEnvVar('BACKTEST_DATA_DIR', './data'),
    outputDir: getEnvVar('BACKTEST_OUTPUT_DIR', './backtest_results'),
    pythonPath: getEnvVar('BACKTRADER_PYTHON_PATH', 'python3'),
    backtraderScriptPath: getEnvVar(
      'BACKTRADER_SCRIPT_PATH',
      './backtest/backtrader_connector.py'
    ),
  },
};

/**
 * Validate configuration
 * Throws error if critical configuration is missing
 */
export function validateConfig(): void {
  const errors: string[] = [];

  if (!config.kite.apiKey) {
    errors.push('KITE_API_KEY is required');
  }

  if (!config.kite.apiSecret) {
    errors.push('KITE_API_SECRET is required');
  }

  if (config.throttle.ordersPerSecond <= 0) {
    errors.push('THROTTLE_ORDERS_PER_SEC must be positive');
  }

  if (config.throttle.ordersPerMinute <= 0) {
    errors.push('THROTTLE_ORDERS_PER_MIN must be positive');
  }

  if (errors.length > 0) {
    throw new Error(`Configuration validation failed:\n${errors.join('\n')}`);
  }
}

export default config;
