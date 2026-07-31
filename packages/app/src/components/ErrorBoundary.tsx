import { Component, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: React.ErrorInfo) {
    console.error(
      "[ErrorBoundary] Uncaught render error:",
      error,
      info.componentStack,
    );
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center py-20 px-4 text-center">
          <h2 className="text-xl font-bold text-zinc-800 mb-2">
            Something went wrong
          </h2>
          <p className="text-zinc-500 mb-4">
            An unexpected error occurred. Please try again.
          </p>
          <button
            onClick={() => this.setState({ hasError: false })}
            className="px-4 py-2 bg-purple-800 text-white rounded-lg hover:bg-purple-700 transition-colors"
          >
            Try again
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
