import {
  Check,
  ChevronDown,
  Keyboard,
  PanelLeftClose,
  PanelLeftOpen,
} from "lucide-react";
import { useLocation } from "react-router-dom";
import { isMock } from "@/lib/api";
import type { User } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useToast } from "@/providers/Toaster";

interface TopBarProps {
  collapsed: boolean;
  onToggle: () => void;
  user?: User;
  users?: User[];
  onSelectUser: (id: string) => void;
}

function pageLabel(pathname: string): string {
  if (pathname === "/") return "总览";
  if (pathname.startsWith("/train")) return "训练";
  if (pathname.startsWith("/actions")) return "动作库";
  if (pathname.startsWith("/data")) return "数据";
  if (pathname.startsWith("/settings")) return "设置";
  return "";
}

export function TopBar({
  collapsed,
  onToggle,
  user,
  users,
  onSelectUser,
}: TopBarProps) {
  const { pathname } = useLocation();
  const toast = useToast();

  return (
    <header className="flex h-16 shrink-0 items-center gap-3 border-b border-line1 bg-bg0 px-4">
      <button
        type="button"
        aria-label={collapsed ? "展开侧栏" : "折叠侧栏"}
        onClick={onToggle}
        className="flex h-9 w-9 items-center justify-center rounded-[8px] text-text2 transition-colors hover:bg-surface2 hover:text-text1"
      >
        {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
      </button>

      <nav className="flex items-center gap-1.5 text-sm">
        <span className="text-text3">FORM LAB</span>
        <span className="text-text3">/</span>
        <span className="text-text1">{pageLabel(pathname)}</span>
      </nav>

      <div className="ml-auto flex items-center gap-3">
        {/* Mock 模式提示；接入真实后端后改为 health 轮询状态点 */}
        {isMock && (
          <Badge tone="amber">
            <span className="font-mono">Mock 模式</span>
          </Badge>
        )}

        {/* 用户切换 */}
        <details className="group relative">
          <summary className="flex cursor-pointer list-none items-center gap-2 rounded-[8px] px-2 py-1.5 transition-colors hover:bg-surface2 [&::-webkit-details-marker]:hidden">
            <div className="flex h-7 w-7 items-center justify-center rounded-full bg-surface2 text-xs text-text1">
              {user?.initials ?? "—"}
            </div>
            <span className="text-sm text-text1">{user?.name ?? "加载中"}</span>
            <ChevronDown size={14} className="text-text3" />
          </summary>
          <div className="absolute right-0 top-full z-20 mt-2 w-52 rounded-card border border-line1 bg-surface1 p-1 shadow-xl">
            {users?.map((u) => (
              <button
                key={u.id}
                type="button"
                onClick={(e) => {
                  onSelectUser(u.id);
                  e.currentTarget.closest("details")?.removeAttribute("open");
                }}
                className="flex w-full items-center gap-2 rounded-[8px] px-3 py-2 text-left text-sm text-text1 transition-colors hover:bg-surface2"
              >
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-surface2 text-xs">
                  {u.initials}
                </span>
                <span className="flex-1 truncate">{u.name}</span>
                {u.id === user?.id && (
                  <Check size={15} className="text-accent" />
                )}
              </button>
            ))}
          </div>
        </details>

        <Button
          variant="ghost"
          className="h-9 w-9 px-0"
          aria-label="快捷键"
          onClick={() =>
            toast.push("快捷键：空格 开始/暂停 · R 重新开始", "accent")
          }
        >
          <Keyboard size={17} />
        </Button>
      </div>
    </header>
  );
}