import { useState } from "react";
import { isMock } from "@/lib/api";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/Badge";
import { AboutSection } from "./AboutSection";
import { GoalsSection } from "./GoalsSection";
import { ProfileSection } from "./ProfileSection";

type Tab = "profile" | "goals" | "about";

const TABS: { key: Tab; label: string }[] = [
  { key: "profile", label: "个人档案" },
  { key: "goals", label: "每日目标" },
  { key: "about", label: "关于与运行信息" },
];

export function SettingsPage() {
  const [tab, setTab] = useState<Tab>("profile");

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-medium text-text1">设置</h1>
        <p className="mt-1 text-sm text-text3">管理用户、每日目标与运行信息。</p>
      </div>

      <div className="flex gap-1 rounded-card border border-line1 bg-surface1 p-1">
        {TABS.map((t) => (
          <button
            key={t.key}
            type="button"
            onClick={() => setTab(t.key)}
            className={cn(
              "flex-1 rounded-[10px] px-4 py-2 text-sm font-medium transition-colors duration-[120ms] ease-form",
              tab === t.key
                ? "bg-surface2 text-text1"
                : "text-text2 hover:text-text1",
            )}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="flex items-center gap-2">
        {isMock ? (
          <>
            <Badge tone="amber">Mock 模式</Badge>
            <span className="text-xs text-text3">
              演示数据，训练记录不会落盘。想要真实数据先启动后端。
            </span>
          </>
        ) : (
          <>
            <Badge tone="mint">已连接判定服务</Badge>
            <span className="text-xs text-text3">
              用户、训练记录、目标都来自本地后端（data/users/）。
            </span>
          </>
        )}
      </div>

      {tab === "profile" && <ProfileSection />}
      {tab === "goals" && <GoalsSection />}
      {tab === "about" && <AboutSection />}
    </div>
  );
}