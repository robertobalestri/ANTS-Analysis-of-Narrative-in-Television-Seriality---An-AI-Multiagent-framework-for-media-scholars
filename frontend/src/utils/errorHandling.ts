export class AppError extends Error {
  constructor(
    message: string,
    public code?: string,
    public statusCode?: number,
    public details?: Record<string, unknown>
  ) {
    super(message);
    this.name = 'AppError';
  }
}

export const handleError = (error: unknown): AppError => {
  if (error instanceof AppError) {
    return error;
  }

  if (error instanceof Error) {
    return new AppError(error.message);
  }

  return new AppError('An unknown error occurred');
};

export const isAppError = (error: unknown): error is AppError => {
  return error instanceof AppError && !!error.statusCode;
};

export interface ErrorMonitoringContext {
  componentStack?: string | null;
  source?: string;
}

export interface ErrorMonitoringPayload {
  name: string;
  message: string;
  code?: string;
  statusCode?: number;
  details?: Record<string, unknown>;
  componentStack?: string | null;
  source?: string;
  timestamp: string;
}

export const reportErrorToMonitoring = (error: unknown, context: ErrorMonitoringContext = {}): void => {
  const appError = handleError(error);
  const payload: ErrorMonitoringPayload = {
    name: appError.name,
    message: appError.message,
    code: appError.code,
    statusCode: appError.statusCode,
    details: appError.details,
    ...context,
    timestamp: new Date().toISOString()
  };

  console.error('MONITORING_ERROR', payload);

  if (typeof window !== 'undefined' && typeof window.dispatchEvent === 'function') {
    window.dispatchEvent(
      new CustomEvent('app:error', {
        detail: payload
      })
    );
  }
};