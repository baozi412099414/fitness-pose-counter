import { useRef } from "react";
import { Copy } from "lucide-react";
import type { NewActionDraft, SaveResult } from "@/lib/types";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { useToast } from "@/providers/Toaster";
import {
  partLabel,
  signalLabel,
  unitOf,
} from "../humanize";

interface Props {
  draft: NewActionDraft;
  result?: SaveResult;
  saving: boolean;
  onSave: () => void;
  onDone: (id: string) => void;
  onReset: () => void;
  goToStep: (s: number) => void;
}

function stepForField(field?: string): number {
  if (!field) return 0;
  if (field.startsWith("quality")) return 2;
  if (field.startsWith("signal")) return 1;
  return 0;
}

function SummaryCard({ draft }: { draft: NewActionDraft }) {
  const unit = unitOf(draft.signal);
  const enter = draft.first === "lo" ? draft.lo : draft.hi;
  const count = draft.first === "lo" ? draft.hi : draft.lo;
  const ruleCount =
    (draft.depth.enabled ? 1 : 0) + (draft.straight.enabled ? 1 : 0);

  return (
    <Card title="保存前请确认" subtitle="服务端会做最终校验，以校验结果为准">
      <dl className="space-y-3 text-sm">
        <div>
          <dt className="text-xs text-text3">名称 / ID</dt>
          <dd className="mt-0.5">
            {draft.name}{" "}
            <span className="font-mono text-text3">{draft.id}</span>
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text3">机位</dt>
          <dd className="mt-0.5">{draft.camera_side === "侧" ? "侧面" : "正面"}</dd>
        </div>
        <div>
          <dt className="text-xs text-text3">判定信号</dt>
          <dd className="mt-0.5">
            {signalLabel(draft.signal)} · {partLabel(draft.points)}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text3">阈值</dt>
          <dd className="mt-0.5">
            进入 {enter}
            {unit} · 计一次 {count}
            {unit}
          </dd>
        </div>
        <div>
          <dt className="text-xs text-text3">质量规则</dt>
          <dd className="mt-0.5">{ruleCount} 条</dd>
        </div>
      </dl>
    </Card>
  );
}

export function SaveStep({
  draft,
  result,
  saving,
  onSave,
  onDone,
  onReset,
  goToStep,
}: Props) {
  const toast = useToast();
  const jsonRef = useRef<HTMLDetailsElement>(null);

  // 成功
  if (result?.ok && result.detail) {
    const raw = {
      id: result.detail.id,
      name: result.detail.name,
      camera_side: result.detail.camera_side,
      calibrate: result.detail.calibrate,
      counter: result.detail.counter,
      quality: result.detail.quality,
    };
    const json = JSON.stringify(raw, null, 2);
    const copy = async () => {
      try {
        await navigator.clipboard.writeText(json);
        toast.push("已复制配置 JSON", "accent");
      } catch {
        toast.push("复制失败", "coral");
      }
    };

    return (
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 flex flex-col gap-5 lg:col-span-8">
          <Card title="保存成功" subtitle="动作库已自动刷新（训练页待接入）">
            <dl className="space-y-3 text-sm">
              <div>
                <dt className="text-xs text-text3">保存路径</dt>
                <dd className="mt-0.5 font-mono text-text1">
                  {result.detail.file_path}
                </dd>
              </div>
              <div>
                <dt className="text-xs text-text3">校验状态</dt>
                <dd className="mt-0.5">
                  <Badge tone="mint">校验通过</Badge>
                </dd>
              </div>
              <div>
                <dt className="text-xs text-text3">警告</dt>
                <dd className="mt-0.5">
                  {result.warnings.length > 0 ? (
                    <ul className="space-y-1 text-amber">
                      {result.warnings.map((w, i) => (
                        <li key={i}>⚠ {w}</li>
                      ))}
                    </ul>
                  ) : (
                    <span className="text-text3">无</span>
                  )}
                </dd>
              </div>
            </dl>
          </Card>

          <Card title="配置 JSON 预览">
            <details ref={jsonRef} className="group">
              <summary className="flex cursor-pointer list-none items-center justify-between [&::-webkit-details-marker]:hidden">
                <span className="text-sm text-text2">展开 / 折叠</span>
                <button
                  type="button"
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    void copy();
                  }}
                  className="flex items-center gap-1 rounded-[6px] px-2 py-1 text-xs text-text2 transition-colors hover:bg-surface2 hover:text-text1"
                >
                  <Copy size={13} />
                  复制
                </button>
              </summary>
              <pre className="mt-3 max-h-80 overflow-auto rounded-[10px] border border-line1 bg-bg0 p-3 font-mono text-xs leading-relaxed text-text2">
                {json}
              </pre>
            </details>
          </Card>
        </div>

        <div className="col-span-12 lg:col-span-4">
          <Card title="下一步">
            <div className="flex flex-col gap-3">
              <Button variant="primary" onClick={() => onDone(result.detail!.id)}>
                完成并查看
              </Button>
              <Button variant="secondary" onClick={onReset}>
                再建一个
              </Button>
            </div>
          </Card>
        </div>
      </div>
    );
  }

  // 失败
  if (result && !result.ok) {
    return (
      <div className="grid grid-cols-12 gap-6">
        <div className="col-span-12 flex flex-col gap-5 lg:col-span-8">
          <Card
            title="校验未通过"
            subtitle={`发现 ${result.errors.length} 处问题，配置未保存`}
          >
            <ul className="space-y-1">
              {result.errors.map((e, i) => (
                <li key={i}>
                  <button
                    type="button"
                    onClick={() => goToStep(stepForField(e.field))}
                    className="block w-full rounded-[8px] px-3 py-2 text-left text-sm text-coral transition-colors hover:bg-coral/10"
                  >
                    ✖ {e.message}
                    <span className="ml-2 text-xs text-text3">去修改 →</span>
                  </button>
                </li>
              ))}
            </ul>
          </Card>
        </div>
        <div className="col-span-12 lg:col-span-4">
          <Card title="提示">
            <p className="text-sm text-text2">
              点击错误行可跳回对应步骤；修正后回到本页重新保存。
            </p>
          </Card>
        </div>
      </div>
    );
  }

  // 初始：待保存
  return (
    <div className="grid grid-cols-12 gap-6">
      <div className="col-span-12 flex flex-col gap-5 lg:col-span-8">
        <SummaryCard draft={draft} />
        <div className="flex items-center gap-3">
          <Button variant="primary" onClick={onSave} disabled={saving}>
            {saving ? "校验中…" : "校验并保存"}
          </Button>
          <span className="text-xs text-text3">
            最终以服务端 validate_config 的结果为准，页面不自判「合法」
          </span>
        </div>
      </div>
      <div className="col-span-12 lg:col-span-4">
        <Card title="说明">
          <p className="text-sm text-text2">
            本轮为 mock：不会写盘 configs/*.json，保存后动作库立即出现新卡片、详情可直接查看。
          </p>
        </Card>
      </div>
    </div>
  );
}