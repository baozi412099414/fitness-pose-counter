import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}
interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("ErrorBoundary caught:", error, info);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex min-h-screen items-center justify-center bg-bg0 p-8">
          <div className="max-w-sm rounded-card border border-line1 bg-surface1 p-6 text-center">
            <p className="text-lg text-text1">页面出错了</p>
            <p className="mt-2 text-sm text-text3">
              {this.state.error.message}
            </p>
            <button
              type="button"
              onClick={() => this.setState({ error: null })}
              className="mt-5 inline-flex h-10 items-center justify-center rounded-[10px] bg-accent px-4 text-sm font-medium text-accentInk"
            >
              重试
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}