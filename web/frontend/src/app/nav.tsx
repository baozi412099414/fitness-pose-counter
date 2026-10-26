import {
  Activity,
  BarChart3,
  LayoutDashboard,
  Layers,
  Settings,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  key: string;
  label: string;
  path: string;
  icon: LucideIcon;
}

export const NAV_ITEMS: NavItem[] = [
  { key: "overview", label: "总览", path: "/", icon: LayoutDashboard },
  { key: "train", label: "训练", path: "/train", icon: Activity },
  { key: "actions", label: "动作库", path: "/actions", icon: Layers },
  { key: "data", label: "数据", path: "/data", icon: BarChart3 },
  { key: "settings", label: "设置", path: "/settings", icon: Settings },
];