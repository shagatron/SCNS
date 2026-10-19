import { Component, type ReactNode } from 'react'

// A failed lazy map chunk/render must never take down the text route planner.
export default class MapFailureBoundary extends Component<{ children: ReactNode; message?: string }, { failed: boolean }> {
  state = { failed: false }
  static getDerivedStateFromError() { return { failed: true } }
  render() {
    return this.state.failed ? <div role="alert" className="error-box"><strong>Map viewer unavailable</strong><p>{this.props.message ?? 'Use the place list and text directions. Reloading requests the viewer again; GPS confirmation must be renewed.'}</p><button onClick={() => window.location.reload()}>Reload map viewer</button></div> : this.props.children
  }
}
