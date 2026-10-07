import { Component, StrictMode, type ReactNode } from 'react';
import { createRoot } from 'react-dom/client';
import { App } from './app/App';
import './styles.css';

class AppErrorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  render() {
    if (this.state.failed)
      return (
        <main>
          <div className="empty-state">
            <h1>页面暂时无法显示</h1>
            <p>请重新加载工作台。未接入服务前，示例数据会在刷新后恢复。</p>
            <button className="button primary" onClick={() => window.location.reload()}>
              重新加载
            </button>
          </div>
        </main>
      );
    return this.props.children;
  }
}

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <AppErrorBoundary>
      <App />
    </AppErrorBoundary>
  </StrictMode>,
);
