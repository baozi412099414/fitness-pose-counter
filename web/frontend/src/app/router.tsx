import { createBrowserRouter, Navigate } from "react-router-dom";
import { AppShell } from "@/app/layout/AppShell";
import { StyleGuidePage } from "@/app/styleguide/StyleGuidePage";
import { OverviewPage } from "@/features/overview/OverviewPage";
import { ActionsPage } from "@/features/actions/ActionsPage";
import { ActionDetailPage } from "@/features/actions/ActionDetailPage";
import { NewActionPage } from "@/features/actions/new/NewActionPage";
import { SettingsPage } from "@/features/settings/SettingsPage";
import { DataPage } from "@/features/data/DataPage";
import { TrainPage } from "@/features/train/TrainPage";

export const router = createBrowserRouter([
  // /styleguide 独立于 AppShell，保留全屏左侧目录布局
  { path: "/styleguide", element: <StyleGuidePage /> },
  {
    element: <AppShell />,
    children: [
      { path: "/", element: <OverviewPage /> },
      { path: "/train", element: <TrainPage /> },
      { path: "/train/:id", element: <TrainPage /> },
      { path: "/actions", element: <ActionsPage /> },
      { path: "/actions/new", element: <NewActionPage /> },
      { path: "/actions/:id", element: <ActionDetailPage /> },
      { path: "/data", element: <DataPage /> },
      { path: "/settings", element: <SettingsPage /> },
    ],
  },
  { path: "*", element: <Navigate to="/" replace /> },
]);