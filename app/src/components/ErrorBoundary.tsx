import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
}

interface State {
  error: Error | null;
}

export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="flex h-screen w-screen items-center justify-center" style={{ background: "var(--color-bg)" }}>
          <div className="max-w-md rounded-lg border p-6 text-center" style={{ borderColor: "var(--color-border)", background: "var(--color-surface)" }}>
            <h1 className="text-base font-semibold" style={{ color: "var(--color-danger)" }}>
              Something went wrong
            </h1>
            <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>
              {this.state.error.message || "An unexpected error occurred in the interface."}
            </p>
            <button
              className="mt-4 rounded-md px-4 py-2 text-sm font-medium text-white"
              style={{ background: "var(--color-primary)" }}
              onClick={() => {
                this.setState({ error: null });
                window.location.href = "/";
              }}
            >
              Reload Overview
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
