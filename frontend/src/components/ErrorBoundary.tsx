import { Component, type ErrorInfo, type ReactNode } from 'react';
import { Box, Heading, Text, Button, VStack, Code, useColorModeValue } from '@chakra-ui/react';
import { reportErrorToMonitoring } from '../utils/errorHandling';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
  error?: Error;
}

function ErrorFallback({ error, onRetry }: { error?: Error; onRetry: () => void }) {
  const background = useColorModeValue('white', 'gray.800');
  const borderColor = useColorModeValue('red.200', 'red.500');
  const mutedText = useColorModeValue('gray.600', 'gray.300');

  return (
    <Box p={8} bg={background} borderRadius="lg" borderWidth="1px" borderColor={borderColor} shadow="sm">
      <VStack spacing={4} align="stretch" textAlign="left">
        <Heading size="md">This section hit an unexpected error.</Heading>
        <Text color={mutedText}>
          Try rendering this section again. If the problem persists, reload the page and retry the last action.
        </Text>
        {error?.message && <Code whiteSpace="pre-wrap">{error.message}</Code>}
        <Box>
          <Button onClick={onRetry}>Try again</Button>
          <Button ml={3} variant="outline" onClick={() => window.location.reload()}>
            Reload page
          </Button>
        </Box>
      </VStack>
    </Box>
  );
}

export class ErrorBoundary extends Component<Props, State> {
  public state: State = {
    hasError: false
  };

  public static getDerivedStateFromError(error: Error): State {
    return { hasError: true, error };
  }

  public componentDidCatch(error: Error, errorInfo: ErrorInfo) {
    reportErrorToMonitoring(error, {
      source: 'ErrorBoundary',
      componentStack: errorInfo.componentStack
    });
  }

  private handleRetry = () => {
    this.setState({ hasError: false, error: undefined });
  };

  public render() {
    if (this.state.hasError) {
      return <ErrorFallback error={this.state.error} onRetry={this.handleRetry} />;
    }

    return this.props.children;
  }
}
