import { NavLink } from "react-router-dom";
import { cn } from "@/lib/cn";
import type { User } from "@/lib/types";
import { NAV_ITEMS } from "@/app/nav";

interface SidebarProps {
  user?: User;
  collapsed: boolean;
}

export function Sidebar({ user, collapsed }: SidebarProps) {
  return (
    <aside
      className="hidden shrink-0 flex-col border-r border-line1 bg-bg0 transition-[width] duration-200 ease-form lg:flex"
      style={{ width: collapsed ? 84 : 220 }}
    >
      {/* 品牌区 */}
      <div className="flex h-16 items-center border-b border-line1 px-5">
        {collapsed ? (
          <span className="font-num text-xl leading-none text-accent">F</span>
        ) : (
          <span className="font-num text-[22px] leading-none text-text1">
            FORM LAB
          </span>
        )}
      </div>

      {/* 导航 */}
      <nav className="flex flex-1 flex-col gap-1 p-3">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.key}
              to={item.path}
              end={item.path === "/"}
              title={collapsed ? item.label : undefined}
              className="rounded-[8px]"
            >
              {({ isActive }) => (
                <div
                  className={cn(
                    "relative flex items-center gap-3 rounded-[8px] px-3 py-2.5 transition-colors duration-[120ms] ease-form",
                    isActive
                      ? "bg-surface2 text-text1"
                      : "text-text2 hover:bg-surface1 hover:text-text1",
                  )}
                >
                  {isActive && (
                    <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-full bg-accent" />
                  )}
                  <Icon size={18} className="shrink-0" />
                  {!collapsed && <span className="text-sm">{item.label}</span>}
                </div>
              )}
            </NavLink>
          );
        })}
      </nav>

      {/* 当前用户 */}
      <div
        className={cn(
          "flex items-center gap-3 border-t border-line1 p-3",
          collapsed && "justify-center",
        )}
      >
        <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface2 text-xs text-text1">
          {user?.initials ?? "—"}
        </div>
        {!collapsed && (
          <div className="flex min-w-0 flex-col">
            <span className="truncate text-sm text-text1">{user?.name}</span>
            <span className="text-xs text-text3">当前用户</span>
          </div>
        )}
      </div>
    </aside>
  );
}