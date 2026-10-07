import { Suspense, lazy, useEffect } from 'react';
import {
  BrowserRouter,
  Link,
  Outlet,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from 'react-router-dom';
import { AppShell } from './AppShell';
import { WorkspaceProvider } from './WorkspaceProvider';
import { useWorkspace } from './workspace-context';
import { createWorkspaceRepository } from '../data/repository';
import { DashboardPage } from '../pages/DashboardPage';
import { EmptyState } from '../components/ui';
import { WorkspaceDialogs } from '../features/Details';

const LibraryPage = lazy(() =>
  import('../pages/LibraryPage').then((module) => ({ default: module.LibraryPage })),
);
const TasksPage = lazy(() =>
  import('../pages/TasksPage').then((module) => ({ default: module.TasksPage })),
);
const StudioPage = lazy(() =>
  import('../pages/StudioPage').then((module) => ({ default: module.StudioPage })),
);
const PublishPage = lazy(() =>
  import('../pages/PublishPage').then((module) => ({ default: module.PublishPage })),
);
const SettingsPage = lazy(() =>
  import('../pages/SettingsPage').then((module) => ({ default: module.SettingsPage })),
);

const repository = createWorkspaceRepository(window.location.search);

function DemoQuery() {
  const location = useLocation();
  const navigate = useNavigate();
  useEffect(() => {
    if (repository.mode !== 'demo') return;
    const params = new URLSearchParams(location.search);
    if (params.get('demo') === '1') return;
    params.set('demo', '1');
    void navigate({ ...location, search: params.toString() }, { replace: true });
  }, [location, navigate]);
  return null;
}

function PageContent() {
  const { snapshot } = useWorkspace();
  return (
    <>
      <Suspense
        fallback={
          <div className="loading-state" role="status">
            正在打开页面…
          </div>
        }
      >
        <Outlet />
      </Suspense>
      {snapshot && <WorkspaceDialogs />}
    </>
  );
}

export function App() {
  return (
    <BrowserRouter>
      <DemoQuery />
      <WorkspaceProvider repository={repository}>
        <Routes>
          <Route element={<AppShell />}>
            <Route element={<PageContent />}>
              <Route index element={<DashboardPage />} />
              <Route path="library" element={<LibraryPage />} />
              <Route path="tasks" element={<TasksPage />} />
              <Route path="studio" element={<StudioPage />} />
              <Route path="publish" element={<PublishPage />} />
              <Route path="settings" element={<SettingsPage />} />
              <Route
                path="*"
                element={
                  <EmptyState title="页面未找到" description="这个地址不在当前工作台中。">
                    <Link className="button primary" to="/">
                      返回工作台
                    </Link>
                  </EmptyState>
                }
              />
            </Route>
          </Route>
        </Routes>
      </WorkspaceProvider>
    </BrowserRouter>
  );
}
