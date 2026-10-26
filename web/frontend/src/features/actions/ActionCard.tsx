import { Link } from "react-router-dom";
import type { Action } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { ActionGlyph } from "./ActionGlyph";

/**
 * 动作库卡片：线稿图标 + 名称 + id + 标签（机位/信号类型/规则数）
 * + 阈值摘要 + 校验状态。hover 荧光绿描边 + 图标轻微上移。
 */
export function ActionCard({ action }: { action: Action }) {
  const v = action.validation;
  const hasIssue = v.error_count > 0 || v.warning_count > 0;

  return (
    <Link
      to={`/actions/${action.id}`}
      className="group flex flex-col rounded-card border border-line1 bg-surface1 p-5 transition-colors duration-[120ms] hover:border-accent"
    >
      <div className="mb-4 flex items-start justify-between">
        <div className="flex h-12 w-12 items-center justify-center rounded-[12px] bg-surface2 transition-transform duration-[120ms] group-hover:-translate-y-0.5">
          <ActionGlyph actionId={action.id} size={28} />
        </div>
        <span
          className={
            v.ok
              ? "flex items-center gap-1.5 text-xs text-mint"
              : "flex items-center gap-1.5 text-xs text-coral"
          }
        >
          <span className="inline-block h-2 w-2 rounded-full bg-current" />
          {v.ok
            ? "通过"
            : `${v.error_count + v.warning_count} 个问题`}
        </span>
      </div>

      <div className="flex items-baseline gap-2">
        <span className="text-[24px] leading-none text-text1">{action.name}</span>
        <span className="font-mono text-xs text-text3">{action.id}</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <Badge tone={action.camera_side === "side" ? "cyan" : "amber"}>
          {action.camera_side === "side" ? "侧方" : "正面"}
        </Badge>
        <Badge tone="neutral">{action.signal_kind}</Badge>
        <Badge tone="neutral">{action.rule_count} 条规则</Badge>
      </div>

      <p className="mt-3 font-mono text-sm text-text2">{action.thresholds}</p>

      {hasIssue && !v.ok && (
        <div className="mt-3 rounded-[8px] border border-coral/30 bg-coral/[0.08] px-3 py-2 text-xs text-coral">
          {v.error_count} 错误 · {v.warning_count} 警告
        </div>
      )}
    </Link>
  );
}