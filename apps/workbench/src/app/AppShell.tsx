import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useWorkspace } from './workspace-context';
import { Icon, type IconName } from '../components/Icon';
import { Dialog } from '../components/Dialog';
import { Button, EmptyState, IconButton, Notice } from '../components/ui';
import { formatDate } from '../domain/workspace';

const routes: { path: string; title: string; icon: IconName }[] = [
  { path: '/', title: '工作台', icon: 'home' },
  { path: '/library', title: '素材库', icon: 'folder' },
  { path: '/tasks', title: '任务中心', icon: 'tasks' },
  { path: '/studio', title: '混剪工作室', icon: 'scissors' },
  { path: '/publish', title: '成片与发布', icon: 'send' },
  { path: '/settings', title: '设置', icon: 'settings' },
];

function Navigation({ onNavigate }: { onNavigate?: () => void }) {
  const { snapshot } = useWorkspace();
  const count =
    snapshot?.tasks.filter((task) => task.status === 'running' || task.status === 'queued')
      .length ?? 0;
  return (
    <nav className="navigation" aria-label="主导航">
      {routes.map(({ path, title, icon }) => (
        <NavLink
          key={path}
          to={path}
          end={path === '/'}
          title={title}
          onClick={onNavigate}
          className={({ isActive }) =>
            `nav-link ${isActive ? 'active' : ''} ${path === '/settings' ? 'settings-link' : ''}`
          }
        >
          <Icon name={icon} />
          <span>{title}</span>
          {path === '/tasks' && count > 0 && <span className="nav-count">{count}</span>}
        </NavLink>
      ))}
    </nav>
  );
}

export function AppShell() {
  const location = useLocation();
  const { snapshot, loading, error, refresh, mode } = useWorkspace();
  const live = mode === 'live';
  const online = live && !!snapshot && !error;
  const [panel, setPanel] = useState<'guide' | 'activity' | 'navigation' | null>(null);
  const title = routes.find((route) => route.path === location.pathname)?.title ?? '页面未找到';
  useEffect(() => {
    document.title = `${title} · 镜流工坊`;
    window.scrollTo(0, 0);
    document.querySelector<HTMLElement>('main')?.focus({ preventScroll: true });
  }, [location.pathname, title]);
  return (
    <>
      <a className="skip-link" href="#main">
        跳转到主要内容
      </a>
      <aside className="sidebar">
        <Link className="brand" to="/" aria-label="镜流工坊首页">
          <span className="brand-mark">
            <svg viewBox="0 0 36 36" aria-hidden="true">
              <path d="M9 8v20l18-10Z" fill="currentColor" />
              <path
                d="M5 11v14M30 11v14"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
              />
            </svg>
          </span>
          <span>
            镜流工坊<small>JINGFLOW STUDIO</small>
          </span>
        </Link>
        <div className="workspace-switch">
          <span className="workspace-avatar">Q</span>
          <span>
            青序内容工作室<small>本地工作空间</small>
          </span>
          <span className="workspace-local">LOCAL</span>
        </div>
        <p className="nav-label">创作空间</p>
        <Navigation />
        <div className="sidebar-bottom">
          <div className="local-status">
            <span className="status-dot" />
            本地引擎<span>{online ? '已连接' : live ? '未连接' : '演示模式'}</span>
          </div>
          <button className="sidebar-help" onClick={() => setPanel('guide')}>
            <Icon name="help" />
            使用指南<span>↗</span>
          </button>
          <div className="profile">
            <span className="avatar">QX</span>
            <span>
              我的工作空间
              <small>
                {live ? `本地服务 · ${snapshot?.service?.version ?? '等待连接'}` : '演示版 · v0.1'}
              </small>
            </span>
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div className="breadcrumb">
            <IconButton
              className="menu-button"
              label="展开导航"
              icon="menu"
              onClick={() => setPanel('navigation')}
            />
            <span>工作空间</span>
            <span className="slash">/</span>
            <strong>{title}</strong>
          </div>
          <div className="topbar-right">
            <span className="demo-badge">
              <span />
              {live
                ? online
                  ? '真实数据 · 本地服务已连接'
                  : '真实模式 · 服务未连接'
                : '示例数据 · 演示模式'}
            </span>
            <IconButton label="查看动态" icon="bell" onClick={() => setPanel('activity')} />
            <span className="top-avatar">Q</span>
          </div>
        </header>
        <main id="main" tabIndex={-1}>
          {loading && !snapshot ? (
            <div className="loading-state" role="status" aria-live="polite">
              <span className="loading-line" />
              正在加载工作空间…
            </div>
          ) : error && !snapshot ? (
            <EmptyState icon="info" title="工作空间暂时无法加载" description={error}>
              <Button onClick={refresh} icon="refresh">
                重新加载
              </Button>
            </EmptyState>
          ) : (
            snapshot && (
              <div className="page" key={location.pathname}>
                {error && (
                  <Notice warm>
                    后台刷新失败，保留上次数据：{error}{' '}
                    <Button className="small" onClick={refresh}>
                      重试连接
                    </Button>
                  </Notice>
                )}
                <Outlet />
              </div>
            )
          )}
        </main>
        <footer className="app-footer">
          <span>JINGFLOW STUDIO</span>
          <span>本地视频制作工作台</span>
          <span>FRONTEND / 0.1</span>
        </footer>
      </div>
      {panel === 'navigation' && (
        <Dialog title="创作空间" onClose={() => setPanel(null)}>
          <div className="mobile-navigation">
            <Navigation onNavigate={() => setPanel(null)} />
          </div>
        </Dialog>
      )}
      {panel === 'guide' && (
        <Dialog
          title="从素材到成片"
          subtitle="工作台使用指南"
          onClose={() => setPanel(null)}
          footer={
            <Button variant="primary" onClick={() => setPanel(null)}>
              开始使用
            </Button>
          }
        >
          <ol className="guide-list">
            <li>
              <strong>选择素材</strong>
              <p>浏览素材或选择本地视频，创建处理任务。</p>
            </li>
            <li>
              <strong>查看任务</strong>
              <p>跟踪队列、处理阶段和结果，处理失败任务。</p>
            </li>
            <li>
              <strong>混剪与发布</strong>
              <p>固定选片方案，区分预览、剪映草稿和最终成片，再确认发布信息。</p>
            </li>
          </ol>
          <Notice>
            {live
              ? '任务由本地 Python 服务串行执行。发布需先在设置中配对 Chrome 插件，选择已登录账号并逐条确认。预填会停在最终提交前；结果未知时请人工核查，不要重复发布。'
              : '当前使用内存示例数据。操作不会运行视频处理或真实发布，刷新页面会恢复示例。'}
          </Notice>
        </Dialog>
      )}
      {panel === 'activity' && (
        <Dialog
          title="工作空间动态"
          subtitle={live ? '最近任务事件 · 服务端状态' : '最近任务事件 · 示例数据'}
          onClose={() => setPanel(null)}
        >
          {snapshot?.tasks.slice(0, 5).map((task) => (
            <div className="activity-row" key={task.id}>
              <Icon name={task.kind === 'mix' ? 'scissors' : 'tasks'} />
              <div>
                {task.name}
                <small>
                  {task.stage} · {formatDate(task.events.at(-1)?.at ?? task.createdAt)}
                </small>
              </div>
            </div>
          ))}
          {!snapshot?.tasks.length && (
            <EmptyState title="暂无动态" description="创建任务后会在这里显示更新。" />
          )}
        </Dialog>
      )}
    </>
  );
}
