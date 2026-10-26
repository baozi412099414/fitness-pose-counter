import { useEffect, useMemo, useState } from "react";
import { Link, useBlocker, useNavigate } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft } from "lucide-react";
import { client } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { NewActionDraft, SaveError } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Dialog } from "@/components/ui/Dialog";
import { isValidId, slugifyId } from "../humanize";
import { BasicInfoStep } from "./BasicInfoStep";
import { SignalStep } from "./SignalStep";
import { QualityRulesStep } from "./QualityRulesStep";
import { SaveStep } from "./SaveStep";

const STEPS = ["基本信息", "判定信号", "质量规则", "校验保存"];

function freshDraft(): NewActionDraft {
  return {
    name: "",
    id: "",
    camera_side: "侧",
    calibrate: true,
    cycles_per_rep: 1,
    signal: "angle",
    points: [23, 25, 27],
    lo: 120,
    hi: 150,
    first: "lo",
    min_interval: 0.4,
    enter_hold: 0.06,
    exit_hold: 0.06,
    min_active_duration: 0.2,
    depth: {
      enabled: false,
      threshold: 105,
      tip: "动作幅度不够，再做大一点",
      priority: 80,
    },
    straight: {
      enabled: false,
      threshold: 160,
      tip: "要回到起始姿势，别停在半路",
      priority: 60,
    },
  };
}

export function NewActionPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [step, setStep] = useState(0);
  const [draft, setDraft] = useState<NewActionDraft>(freshDraft);
  const [dirty, setDirty] = useState(false);
  const [idTouched, setIdTouched] = useState(false);

  const actionsQ = useQuery({ queryKey: ["actions"], queryFn: client.getActions });
  const existingIds = useMemo(
    () => new Set((actionsQ.data ?? []).map((a) => a.id)),
    [actionsQ.data],
  );

  const mutation = useMutation({
    mutationFn: (d: NewActionDraft) => client.createAction(d),
    onSuccess: (result) => {
      if (result.ok) {
        setDirty(false);
        queryClient.invalidateQueries({ queryKey: ["actions"] });
        queryClient.invalidateQueries({ queryKey: ["validate-actions"] });
      }
    },
  });

  // 保存失败时的结构化错误，供各步骤标红
  const saveErrors: SaveError[] =
    mutation.data && !mutation.data.ok ? mutation.data.errors : [];

  const update = (patch: Partial<NewActionDraft>) => {
    setDraft((d) => ({ ...d, ...patch }));
    setDirty(true);
    // 任何改动都让上一次保存/校验结果失效
    if (mutation.data) mutation.reset();
  };

  const canLeave = (s: number): boolean => {
    if (s === 0) {
      return (
        draft.name.trim() !== "" &&
        isValidId(draft.id) &&
        !existingIds.has(draft.id)
      );
    }
    if (s === 1) {
      return draft.points.length > 0 && draft.signal !== "" && draft.lo < draft.hi;
    }
    return true;
  };

  const next = () => {
    if (step < 3 && canLeave(step)) setStep((s) => s + 1);
  };

  const resetForm = () => {
    setDraft(freshDraft());
    setIdTouched(false);
    setDirty(false);
    mutation.reset();
    setStep(0);
  };

  const blocker = useBlocker(dirty);

  // Enter = 下一步（焦点在按钮/下拉/文本域时不抢键，避免和控件自身行为冲突）
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Enter" || e.isComposing) return;
      if (blocker.state === "blocked" || step >= 3) return;
      const el = document.activeElement;
      if (
        el instanceof HTMLButtonElement ||
        el instanceof HTMLTextAreaElement ||
        el instanceof HTMLSelectElement
      ) {
        return;
      }
      if (canLeave(step)) {
        e.preventDefault();
        setStep((s) => s + 1);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, draft, existingIds, blocker.state]);

  const goToStep = (s: number) => {
    if (s < step) setStep(s);
  };

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to="/actions"
          className="inline-flex items-center gap-1.5 text-sm text-text3 transition-colors hover:text-text1"
        >
          <ArrowLeft size={15} />
          动作库
        </Link>
        <h1 className="mt-2 text-2xl font-medium text-text1">新建动作</h1>
      </div>

      {/* 步骤条 */}
      <ol className="flex flex-wrap items-center gap-2">
        {STEPS.map((label, i) => {
          const active = i === step;
          const done = i < step;
          return (
            <li key={label} className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => goToStep(i)}
                disabled={!done}
                className={cn(
                  "flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs transition-colors",
                  active
                    ? "border-accent/40 bg-accent/10 text-accent"
                    : done
                      ? "border-line1 bg-surface1 text-text1 hover:border-line2"
                      : "cursor-default border-line1 bg-transparent text-text3",
                )}
              >
                <span className="font-num">{i + 1}</span>
                {label}
              </button>
              {i < STEPS.length - 1 && (
                <span className="text-xs text-line2">→</span>
              )}
            </li>
          );
        })}
      </ol>

      {step === 0 && (
        <BasicInfoStep
          draft={draft}
          onChange={update}
          errors={saveErrors}
          existingIds={existingIds}
          onNameChange={(name) => {
            if (!idTouched) {
              setDraft((d) => ({ ...d, name, id: slugifyId(name, [...existingIds]) }));
            } else {
              setDraft((d) => ({ ...d, name }));
            }
            setDirty(true);
            if (mutation.data) mutation.reset();
          }}
          onIdChange={(id) => {
            setIdTouched(true);
            setDraft((d) => ({ ...d, id }));
            setDirty(true);
            if (mutation.data) mutation.reset();
          }}
        />
      )}
      {step === 1 && <SignalStep draft={draft} onChange={update} errors={saveErrors} />}
      {step === 2 && (
        <QualityRulesStep draft={draft} onChange={update} errors={saveErrors} />
      )}
      {step === 3 && (
        <SaveStep
          draft={draft}
          result={mutation.data}
          saving={mutation.isPending}
          onSave={() => mutation.mutate(draft)}
          onDone={(id) => navigate(`/actions/${id}`)}
          onReset={resetForm}
          goToStep={goToStep}
        />
      )}

      {/* 底部导航 */}
      <div className="flex items-center justify-between">
        <Button variant="ghost" disabled={step === 0} onClick={() => setStep(step - 1)}>
          上一步
        </Button>
        {step < 3 && (
          <Button variant="primary" disabled={!canLeave(step)} onClick={next}>
            下一步
          </Button>
        )}
      </div>

      <Dialog
        open={blocker.state === "blocked"}
        onClose={() => blocker.reset?.()}
        title="离开此页？"
        footer={
          <>
            <Button variant="secondary" onClick={() => blocker.reset?.()}>
              留下继续编辑
            </Button>
            <Button variant="danger" onClick={() => blocker.proceed?.()}>
              离开
            </Button>
          </>
        }
      >
        <p className="text-sm text-text2">
          表单尚未保存，离开后本次填写的内容会丢失。
        </p>
      </Dialog>
    </div>
  );
}