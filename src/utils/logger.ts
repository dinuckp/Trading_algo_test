import winston from 'winston';
import path from 'path';
import fs from 'fs';

/**
 * Structured logger using Winston with JSON output support
 * Ensures secrets are never logged and supports correlation IDs
 */

// Sensitive fields that should never be logged
const SENSITIVE_FIELDS = [
  'api_key',
  'api_secret',
  'access_token',
  'request_token',
  'password',
  'secret',
  'authorization',
  'token',
];

/**
 * Recursively redact sensitive fields from objects
 */
function redactSensitiveData(obj: unknown): unknown {
  if (obj === null || obj === undefined) {
    return obj;
  }

  if (Array.isArray(obj)) {
    return obj.map(redactSensitiveData);
  }

  if (typeof obj === 'object') {
    const redacted: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj)) {
      const lowerKey = key.toLowerCase();
      if (SENSITIVE_FIELDS.some(field => lowerKey.includes(field))) {
        redacted[key] = '[REDACTED]';
      } else {
        redacted[key] = redactSensitiveData(value);
      }
    }
    return redacted;
  }

  return obj;
}

/**
 * Custom format that redacts sensitive information
 */
const redactFormat = winston.format((info) => {
  return redactSensitiveData(info) as winston.Logform.TransformableInfo;
});

/**
 * Create logger instance with file and console transports
 */
function createLogger(): winston.Logger {
  const logLevel = process.env.LOG_LEVEL || 'info';
  const logFilePath = process.env.LOG_FILE_PATH || './logs/app.log';
  const useJson = process.env.LOG_JSON === 'true';

  // Ensure log directory exists
  const logDir = path.dirname(logFilePath);
  if (!fs.existsSync(logDir)) {
    fs.mkdirSync(logDir, { recursive: true });
  }

  const formats = [
    winston.format.timestamp({ format: 'YYYY-MM-DD HH:mm:ss' }),
    winston.format.errors({ stack: true }),
    redactFormat(),
  ];

  if (useJson) {
    formats.push(winston.format.json());
  } else {
    formats.push(
      winston.format.printf(({ timestamp, level, message, correlationId, ...meta }) => {
        let log = `${timestamp} [${level.toUpperCase()}]`;
        if (correlationId) {
          log += ` [${correlationId}]`;
        }
        log += `: ${message}`;

        const metaKeys = Object.keys(meta);
        if (metaKeys.length > 0 && metaKeys[0] !== 'timestamp') {
          log += ` ${JSON.stringify(meta)}`;
        }
        return log;
      })
    );
  }

  const logger = winston.createLogger({
    level: logLevel,
    format: winston.format.combine(...formats),
    transports: [
      // File transport for all logs
      new winston.transports.File({
        filename: logFilePath,
        maxsize: 10485760, // 10MB
        maxFiles: 5,
      }),
      // Separate file for errors
      new winston.transports.File({
        filename: path.join(logDir, 'error.log'),
        level: 'error',
        maxsize: 10485760,
        maxFiles: 5,
      }),
    ],
  });

  // Add console transport in development or when not using JSON
  if (process.env.NODE_ENV !== 'production' || !useJson) {
    logger.add(
      new winston.transports.Console({
        format: winston.format.combine(
          winston.format.colorize(),
          winston.format.printf(({ timestamp, level, message, correlationId, ...meta }) => {
            let log = `${timestamp} [${level}]`;
            if (correlationId) {
              log += ` [${correlationId}]`;
            }
            log += `: ${message}`;

            const metaKeys = Object.keys(meta);
            if (metaKeys.length > 0 && metaKeys[0] !== 'timestamp') {
              log += ` ${JSON.stringify(meta, null, 2)}`;
            }
            return log;
          })
        ),
      })
    );
  }

  return logger;
}

// Singleton logger instance
export const logger = createLogger();

/**
 * Create a child logger with a correlation ID for request tracking
 */
export function createChildLogger(correlationId: string): winston.Logger {
  return logger.child({ correlationId });
}

/**
 * Log order events with structured data
 */
export function logOrder(
  level: 'info' | 'warn' | 'error',
  message: string,
  orderData: {
    orderId?: string;
    symbol?: string;
    action?: string;
    quantity?: number;
    price?: number;
    status?: string;
    [key: string]: unknown;
  },
  correlationId?: string
): void {
  const meta = correlationId ? { ...orderData, correlationId } : orderData;
  logger.log(level, message, meta);
}

export default logger;
