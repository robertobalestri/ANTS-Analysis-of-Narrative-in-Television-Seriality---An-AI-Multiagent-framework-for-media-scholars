import { ChakraProvider } from '@chakra-ui/react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest';
import { ErrorBoundary } from './ErrorBoundary';

function Bomb({ shouldThrow }: { shouldThrow: boolean }) {
  if (shouldThrow) {
    throw new Error('Simulated render failure');
  }

  return <div>Recovered content</div>;
}

function TestHarness({ shouldThrow }: { shouldThrow: boolean }) {
  return (
    <ChakraProvider>
      <ErrorBoundary>
        <Bomb shouldThrow={shouldThrow} />
      </ErrorBoundary>
    </ChakraProvider>
  );
}

describe('ErrorBoundary', () => {
  const consoleErrorSpy = vi.spyOn(console, 'error').mockImplementation(() => {});
  const dispatchEventSpy = vi.spyOn(window, 'dispatchEvent');

  beforeEach(() => {
    consoleErrorSpy.mockClear();
    dispatchEventSpy.mockClear();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('shows fallback UI, reports the error, and retries successfully after a simulated render error', async () => {
    let shouldThrow = true;

    const { rerender } = render(<TestHarness shouldThrow={shouldThrow} />);

    expect(await screen.findByText('This section hit an unexpected error.')).toBeInTheDocument();
    expect(screen.getByText('Simulated render failure')).toBeInTheDocument();

    await waitFor(() => {
      expect(consoleErrorSpy).toHaveBeenCalledWith(
        'MONITORING_ERROR',
        expect.objectContaining({
          message: 'Simulated render failure',
          source: 'ErrorBoundary'
        })
      );
    });

    expect(dispatchEventSpy).toHaveBeenCalledWith(
      expect.objectContaining({
        type: 'app:error'
      })
    );

    shouldThrow = false;
    rerender(<TestHarness shouldThrow={shouldThrow} />);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));

    expect(await screen.findByText('Recovered content')).toBeInTheDocument();
  });
});
