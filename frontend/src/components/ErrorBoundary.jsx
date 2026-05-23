import React from "react";

/**
 * Global error boundary - prevents the entire React tree from unmounting
 * when an unexpected render error occurs (e.g. bad toast payload).
 */
export default class ErrorBoundary extends React.Component {
  state = { hasError: false, error: null };

  static getDerivedStateFromError(error) {
    return { hasError: true, error };
  }

  componentDidCatch(error, info) {
    console.error("App error boundary caught:", error, info);
  }

  reset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (!this.state.hasError) return this.props.children;
    return (
      <div className="min-h-screen flex items-center justify-center p-6 bg-[#FAFAFA]" data-testid="error-boundary">
        <div className="max-w-md w-full bg-white border border-zinc-200 rounded-md p-8">
          <div className="overline text-zinc-500 mb-2">Something went wrong</div>
          <h1 className="font-display font-black text-3xl tracking-tight leading-none mb-3">
            We hit a small bump.
          </h1>
          <p className="text-sm text-zinc-600 mb-6 leading-relaxed">
            The page ran into an unexpected error. Click below to recover —
            your data is safe.
          </p>
          <div className="flex gap-2">
            <button
              onClick={() => {
                this.reset();
                window.location.reload();
              }}
              className="flex-1 h-11 bg-zinc-950 hover:bg-zinc-800 text-white rounded-md font-medium"
            >
              Reload page
            </button>
            <button
              onClick={this.reset}
              className="h-11 px-4 border border-zinc-300 hover:bg-zinc-50 rounded-md font-medium text-sm"
            >
              Dismiss
            </button>
          </div>
        </div>
      </div>
    );
  }
}
