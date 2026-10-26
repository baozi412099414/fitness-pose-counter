import type { NewActionDraft, SaveError } from "@/lib/types";
import { cn } from "@/lib/cn";
import { Card } from "@/components/ui/Card";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { NumberStepper } from "@/components/ui/NumberStepper";
import { Switch } from "@/components/ui/Switch";

interface Props {
  draft: NewActionDraft;
  onChange: (patch: Partial<NewActionDraft>) => void;
  errors: SaveError[];
  existingIds: Set<string>;
  onNameChange: (name: string) => void;
  onIdChange: (id: string) => void;
}

export function BasicInfoStep({
  draft,
  onChange,
  errors,
  existingIds,
  onNameChange,
  onIdChange,
}: Props) {
  const err = (f: string) => errors.find((e) => e.field === f)?.message;

  const idConflict = existingIds.has(draft.id);

  return (
    <div className="grid grid-cols-12 gap-6">
      <div className="col-span-12 flex flex-col gap-5 lg:col-span-8">
        <Field label="动作名称" required error={err("name")}>
          <Input
            value={draft.name}
            onChange={(e) => onNameChange(e.target.value)}
            placeholder="如：靠墙静蹲"
            autoFocus
          />
        </Field>

        <Field
          label="动作 ID"
          required
          error={err("id") ?? (idConflict ? `ID「${draft.id}」已存在` : undefined)}
          help="自动从名称生成，可手改；只允许字母、数字、下划线"
        >
          <Input
            value={draft.id}
            onChange={(e) => onIdChange(e.target.value)}
            placeholder="action"
            className="font-mono"
          />
        </Field>

        <Field label="机位" required>
          <div className="grid grid-cols-2 gap-3">
            {(["侧", "正"] as const).map((side) => (
              <button
                key={side}
                type="button"
                onClick={() => onChange({ camera_side: side })}
                className={cn(
                  "rounded-[10px] border p-3 text-left transition-colors",
                  draft.camera_side === side
                    ? "border-accent bg-accent/10"
                    : "border-line1 hover:border-line2",
                )}
              >
                <span className="text-sm text-text1">
                  {side === "侧" ? "侧面" : "正面"}
                </span>
                <span className="mt-0.5 block text-xs text-text3">
                  {side === "侧" ? "适合深蹲、俯卧撑等前后移动" : "适合开合跳等左右张开"}
                </span>
              </button>
            ))}
          </div>
        </Field>

        <Field
          label="校准开关"
          help="只对角度变小类动作有效，如深蹲；开合跳请关闭"
        >
          <Switch
            checked={draft.calibrate}
            onChange={(v) => onChange({ calibrate: v })}
            label={draft.calibrate ? "开启" : "关闭"}
          />
        </Field>

        <Field label="循环次数" help="几个完整往返算 1 次（1 = 单次往复）">
          <NumberStepper
            value={draft.cycles_per_rep}
            onChange={(v) => onChange({ cycles_per_rep: v })}
            min={1}
            max={5}
            step={1}
            unit="次"
          />
        </Field>
      </div>

      <div className="col-span-12 lg:col-span-4">
        <Card title="预览">
          <dl className="space-y-3 text-sm">
            <div>
              <dt className="text-xs text-text3">动作名</dt>
              <dd className="mt-0.5 text-text1">{draft.name || "未命名动作"}</dd>
            </div>
            <div>
              <dt className="text-xs text-text3">机位</dt>
              <dd className="mt-0.5 text-text1">
                {draft.camera_side === "侧" ? "侧面" : "正面"}
              </dd>
            </div>
            <div>
              <dt className="text-xs text-text3">预计规则数</dt>
              <dd className="mt-0.5 text-text1">
                {(draft.depth.enabled ? 1 : 0) + (draft.straight.enabled ? 1 : 0)} 条
              </dd>
            </div>
          </dl>
        </Card>
      </div>
    </div>
  );
}