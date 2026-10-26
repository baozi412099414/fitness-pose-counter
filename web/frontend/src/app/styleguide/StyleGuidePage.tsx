import { useState, type ReactNode } from "react";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { Drawer } from "@/components/ui/Drawer";
import { EmptyState } from "@/components/ui/EmptyState";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { NumberStepper } from "@/components/ui/NumberStepper";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { RuleRow, type RuleRowState } from "@/components/ui/RuleRow";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";
import { Stat } from "@/components/ui/Stat";
import { TipBanner } from "@/components/ui/TipBanner";
import { Toast } from "@/components/ui/Toast";

const NAV = [
  { id: "color", label: "色彩" },
  { id: "type", label: "字体" },
  { id: "scale", label: "字号节奏" },
  { id: "button", label: "按钮" },
  { id: "form", label: "表单" },
  { id: "data", label: "卡片 / 统计 / 徽章" },
  { id: "rulerow", label: "规则行" },
  { id: "misc", label: "环 / 提示 / 空态 / 骨架" },
  { id: "overlay", label: "弹窗 / 抽屉 / Toast" },
];

const SWATCHES: { name: string; hex: string }[] = [
  { name: "bg-0", hex: "#060709" },
  { name: "bg-1", hex: "#0B0D11" },
  { name: "surface-1", hex: "#101318" },
  { name: "surface-2", hex: "#151922" },
  { name: "surface-3", hex: "#1B202A" },
  { name: "line-1", hex: "#232833" },
  { name: "line-2", hex: "#2E3542" },
  { name: "text-1", hex: "#F5F7FA" },
  { name: "text-2", hex: "#A3ACBA" },
  { name: "text-3", hex: "#6C7686" },
  { name: "accent", hex: "#D6FF3F" },
  { name: "accent-ink", hex: "#0A0C05" },
  { name: "cyan", hex: "#6FE3FF" },
  { name: "amber", hex: "#FFB454" },
  { name: "coral", hex: "#FF6B5C" },
  { name: "mint", hex: "#45E0A8" },
];

function Section({
  id,
  index,
  title,
  lead,
  children,
}: {
  id: string;
  index: string;
  title: string;
  lead: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-8 border-t border-line1 py-10 first:border-t-0 first:pt-0">
      <div className="mb-6 flex items-baseline gap-3">
        <span className="font-mono text-xs uppercase tracking-[0.12em] text-text3">
          {index}
        </span>
        <h2 className="text-2xl font-medium text-text1">{title}</h2>
        <p className="text-sm text-text3">{lead}</p>
      </div>
      {children}
    </section>
  );
}

export function StyleGuidePage() {
  const [dialogOpen, setDialogOpen] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [toast, setToast] = useState<{ show: boolean; tone: "accent" | "mint" | "coral" }>(
    { show: false, tone: "accent" },
  );
  const [reps, setReps] = useState(10);

  return (
    <div className="bg-glow bg-noise min-h-screen">
      <div className="mx-auto flex max-w-[1440px]">
        {/* 左侧目录 */}
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 border-r border-line1 px-6 py-8 lg:block">
          <div className="mb-8">
            <p className="font-num text-[32px] leading-none text-text1">FORM LAB</p>
            <p className="mt-1 text-xs uppercase tracking-[0.12em] text-text3">
              形实验室 · 设计规范
            </p>
          </div>
          <nav className="flex flex-col gap-1">
            {NAV.map((n) => (
              <a
                key={n.id}
                href={`#${n.id}`}
                className="rounded-[8px] px-3 py-2 text-sm text-text2 transition-colors hover:bg-surface2 hover:text-text1"
              >
                {n.label}
              </a>
            ))}
          </nav>
        </aside>

        {/* 右侧展示 */}
        <main className="min-w-0 flex-1 px-6 py-10 md:px-10">
          <header className="mb-10">
            <p className="font-ui text-[72px] leading-none text-text1">
              设计规范
            </p>
            <p className="mt-3 max-w-xl text-sm text-text2">
              运动科学仪器 × 专业相机取景器 × F1 遥测面板。克制、精密、爆发力；
              荧光绿只留给「正在发生的事」。
            </p>
          </header>

          {/* 色彩 */}
          <Section id="color" index="01" title="色彩" lead="16 个颜色 token，一屏最多两种强调色">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
              {SWATCHES.map((s) => (
                <div
                  key={s.name}
                  className="overflow-hidden rounded-card border border-line1 bg-surface1"
                >
                  <div className="h-16 border-b border-line1" style={{ backgroundColor: s.hex }} />
                  <div className="px-3 py-2.5">
                    <p className="text-sm text-text1">{s.name}</p>
                    <p className="font-mono text-xs uppercase text-text3">{s.hex}</p>
                  </div>
                </div>
              ))}
            </div>
          </Section>

          {/* 字体 */}
          <Section id="type" index="02" title="字体" lead="display 大数字 / ui 中文 / mono 等宽">
            <div className="grid gap-3 lg:grid-cols-3">
              <div className="rounded-card border border-line1 bg-surface1 p-5">
                <p className="mb-3 text-xs uppercase tracking-[0.12em] text-text3">Display</p>
                <p className="font-num text-[72px] leading-none text-text1">180°</p>
                <p className="mt-2 font-mono text-xs text-text3">Bebas Neue · tabular-nums</p>
              </div>
              <div className="rounded-card border border-line1 bg-surface1 p-5">
                <p className="mb-3 text-xs uppercase tracking-[0.12em] text-text3">Interface</p>
                <p className="text-[28px] leading-tight text-text1">深蹲 · 姿态纠正</p>
                <p className="mt-2 font-mono text-xs text-text3">MiSans / 系统中文栈</p>
              </div>
              <div className="rounded-card border border-line1 bg-surface1 p-5">
                <p className="mb-3 text-xs uppercase tracking-[0.12em] text-text3">Mono</p>
                <p className="font-mono text-[24px] text-cyan">142.3 / 155°</p>
                <p className="mt-2 font-mono text-xs text-text3">Space Grotesk · 等宽</p>
              </div>
            </div>
          </Section>

          {/* 字号节奏 */}
          <Section id="scale" index="03" title="字号节奏" lead="12 → 180，间距 4 的倍数">
            <div className="flex flex-wrap items-end gap-6 rounded-card border border-line1 bg-surface1 p-6">
              {[12, 13, 14, 16, 20, 24, 32, 48, 72, 120].map((px) => (
                <div key={px} className="flex flex-col items-center gap-1">
                  <span
                    className="font-num leading-none text-text1"
                    style={{ fontSize: px }}
                  >
                    Aa
                  </span>
                  <span className="font-mono text-[11px] text-text3">{px}</span>
                </div>
              ))}
            </div>
          </Section>

          {/* 按钮 */}
          <Section id="button" index="04" title="按钮" lead="4 种变体，高 40 / 圆角 10">
            <div className="flex flex-wrap items-center gap-4">
              <Button variant="primary">开始训练</Button>
              <Button variant="secondary">取消</Button>
              <Button variant="ghost">查看日志</Button>
              <Button variant="danger">删除动作</Button>
              <Button variant="primary" disabled>
                已禁用
              </Button>
            </div>
          </Section>

          {/* 表单 */}
          <Section id="form" index="05" title="表单" lead="深色底 + 1px 描边，focus 荧光绿">
            <div className="grid gap-6 lg:grid-cols-2">
              <Field label="动作名称" required htmlFor="sg-name" help="按钮与 HUD 上显示的中文名">
                <Input id="sg-name" placeholder="例如：单手俯卧撑" />
              </Field>
              <Field label="测量部位" error="请选择测量部位">
                <Select defaultValue="">
                  <option value="" disabled>
                    选择一个关节角度
                  </option>
                  <option>左膝角（髋-膝-踝）</option>
                  <option>右肘角（肩-肘-腕）</option>
                </Select>
              </Field>
              <Field label="每组次数" help="每做满一组自动进入休息倒计时">
                <NumberStepper
                  value={reps}
                  onChange={setReps}
                  min={1}
                  max={50}
                  unit="次"
                />
              </Field>
            </div>
          </Section>

          {/* 卡片 / 统计 / 徽章 */}
          <Section id="data" index="06" title="卡片 · 统计 · 徽章" lead="surface-1 + 1px 描边，无阴影">
            <div className="grid gap-4 lg:grid-cols-3">
              <Card title="本次训练" subtitle="深蹲 · 3 组 × 10 次" className="lg:col-span-2">
                <div className="grid grid-cols-3 gap-6">
                  <Stat label="次数" value={30} delta="+12" />
                  <Stat label="平均分" value={78.2} delta="─" deltaTone="mint" />
                  <Stat label="历史最多" value={52} delta="新纪录" />
                </div>
              </Card>
              <Card title="状态" subtitle="语义色只用于小面积">
                <div className="flex flex-wrap gap-2">
                  <Badge tone="accent">进行中</Badge>
                  <Badge tone="mint">达标</Badge>
                  <Badge tone="amber">休息 30s</Badge>
                  <Badge tone="coral">未达标</Badge>
                  <Badge tone="cyan">数据</Badge>
                  <Badge tone="neutral">空闲</Badge>
                </div>
              </Card>
            </div>
          </Section>

          {/* 规则行 */}
          <Section id="rulerow" index="07" title="规则行" lead="失败 coral / 达标 mint / 不可见灰 / 未参与暗灰">
            <div className="flex flex-col gap-3">
              {(
                [
                  { name: "蹲得不够深", value: "112°", limit: "≤ 105°", state: "fail", progress: 0.86 },
                  { name: "站起时腿没伸直", value: "178°", limit: "≥ 160°", state: "pass", progress: 1 },
                  { name: "左腿下蹲幅度不足", value: "—", limit: "≤ 105°", state: "invisible", progress: 0 },
                  { name: "躯干与小腿失配", value: "—", limit: "≤ 60°", state: "unchecked", progress: 0 },
                ] as { name: string; value: string; limit: string; state: RuleRowState; progress: number }[]
              ).map((r) => (
                <RuleRow key={r.name} {...r} />
              ))}
            </div>
          </Section>

          {/* 环 / 提示 / 空态 / 骨架 */}
          <Section id="misc" index="08" title="环 · 提示 · 空态 · 骨架" lead="ProgressRing / TipBanner / EmptyState / Skeleton">
            <div className="grid gap-4 lg:grid-cols-2">
              <Card title="进度环" subtitle="120 / 160px，8px 描边圆头">
                <div className="flex items-center gap-6">
                  <ProgressRing value={78.2} size={120} label="评分" />
                  <ProgressRing value={45} size={160} label="目标" />
                </div>
              </Card>
              <div className="flex flex-col gap-4">
                <TipBanner>收紧核心，头肩髋踝保持一条直线</TipBanner>
                <EmptyState
                  title="还没有训练记录"
                  description="完成一次训练后，这里会显示趋势图、历史评分和错误排行。"
                  action={<Button variant="secondary">开始第一次训练</Button>}
                />
                <div className="flex flex-col gap-3">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-4 w-1/2" />
                </div>
              </div>
            </div>
          </Section>

          {/* 弹窗 / 抽屉 / Toast */}
          <Section id="overlay" index="09" title="弹窗 · 抽屉 · Toast" lead="原生 <dialog>，ESC 关闭，遮罩 70%">
            <div className="flex flex-wrap gap-4">
              <Button variant="primary" onClick={() => setDialogOpen(true)}>
                打开弹窗
              </Button>
              <Button variant="secondary" onClick={() => setDrawerOpen(true)}>
                打开抽屉
              </Button>
              <Button variant="ghost" onClick={() => setToast({ show: true, tone: "accent" })}>
                触发 Toast
              </Button>
            </div>
          </Section>
        </main>
      </div>

      <Dialog
        open={dialogOpen}
        onClose={() => setDialogOpen(false)}
        title="删除动作"
        footer={
          <>
            <Button variant="ghost" onClick={() => setDialogOpen(false)}>
              取消
            </Button>
            <Button variant="danger" onClick={() => setDialogOpen(false)}>
              确认删除
            </Button>
          </>
        }
      >
        <p className="text-sm text-text2">
          删除后该动作的配置将从 <span className="font-mono text-text1">configs/</span>{" "}
          移除，且不可恢复。确定要继续吗？
        </p>
      </Dialog>

      <Drawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        title="动作详情"
      >
        <p className="text-sm text-text2">
          这里是抽屉内容。左侧目录在窄屏下折叠，实时页会提示桌面/横屏。
        </p>
      </Drawer>

      {toast.show && (
        <Toast
          message="已保存动作配置"
          tone={toast.tone}
          onDismiss={() => setToast((t) => ({ ...t, show: false }))}
        />
      )}
    </div>
  );
}