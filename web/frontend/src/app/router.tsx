import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/app/layout/AppShell";
import { StyleGuidePage } from "@/app/styleguide/StyleGuidePage";
import { OverviewPage } from "@/features/overview/OverviewPage";
import { ActionsPage } from "@/features/actions/ActionsPage";
import { ActionDetailPage } from "@/features/actions/ActionDetailPage";
import { PlaceholderPage } from "@/components/placeholder/PlaceholderPage";

export const router = createBrowserRouter([
  // /styleguide 独立于 AppShell，保留全屏左侧目录布局
  { path: "/styleguide", element: <StyleGuidePage /> },
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <OverviewPage /> },
      { path: "/train", element: <PlaceholderPage title="训练" /> },
      { path: "/train/:id", element: <PlaceholderPage title="实时训练" /> },
      { path: "/actions", element: <ActionsPage /> },
      { path: "/actions/new", element: <PlaceholderPage title="新建动作" /> },
      { path: "/actions/:id", element: <ActionDetailPage /> },
      { path: "/data", element: <PlaceholderPage title="训练数据" /> },
      { path: "/settings", element: <PlaceholderPage title="设置" /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);