import type { ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { client } from "@/lib/api";
import { Card } from "@/components/ui/Card";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Skeleton } from "@/components/ui/Skeleton";

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div>
      <dt className="text-xs uppercase tracking-[0.12em] text-text3">{label}</dt>
      <dd className="mt-1 text-sm text-text1">{value}</dd>
    </div>
  );
}

export function AboutSection() {
  const health = useQuery({ queryKey: ["health"], queryFn: client.getHealth });
  const docsUrl = `${health.data?.backend_url ?? "http://127.0.0.1:8000"}/docs`;

  return (
    <div className="flex flex-col gap-6">
      {health.isError && <ErrorBanner onRetry={() => health.refetch()} />}

      <Card title="关于" subtitle="项目与模块信息">
        <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
          <Row label="项目" value="FORM LAB · 健身动作计数与姿态纠正" />
          <Row label="题目编号" value="第 11 题" />
          <Row label="技术栈" value="React + Vite + Tailwind · FastAPI + MediaPipe" />
          <Row label="模型" value="MediaPipe Pose Landmarker lite · 本地部署 · CPU" />
        </dl>
      </Card>

      <Card title="运行信息" subtitle="来自 /api/health">
        {health.isLoading ? (
          <div className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            {[0, 1, 2, 3, 4, 5].map((i) => (
              <Skeleton key={i} className="h-10" />
            ))}
          </div>
        ) : health.data ? (
          <dl className="grid gap-x-8 gap-y-4 sm:grid-cols-2">
            <Row label="版本" value={health.data.version} />
            <Row label="Python" value={health.data.python_version} />
            <Row label="MediaPipe" value={health.data.mediapipe_version} />
            <Row label="模型文件" value={<code className="font-mono text-[13px]">{health.data.model}</code>} />
            <Row label="运行设备" value={health.data.device} />
            <Row
              label="数据目录"
              value={<code className="font-mono text-[13px]">{health.data.data_dir}</code>}
            />
            <Row
              label="配置目录"
              value={<code className="font-mono text-[13px]">{health.data.configs_dir}</code>}
            />
            <Row
              label="后端地址"
              value={<code className="font-mono text-[13px]">{health.data.backend_url}</code>}
            />
          </dl>
        ) : null}
      </Card>

      <Card title="口径说明" subtitle="阈值与模型部署">
        <p className="text-sm leading-relaxed text-text1">
          动作判定阈值依据运动学几何与 ACE/NASM 规范给出工程初值，尚未完成真人视频回归校准；
          系统支持按用户体型与机位重新标定。
        </p>
      </Card>

      <Card title="隐私">
        <p className="text-sm leading-relaxed text-text1">
          摄像头帧仅在内存中推理，不保存视频。
        </p>
      </Card>

      <a
        href={docsUrl}
        target="_blank"
        rel="noreferrer"
        className="inline-flex w-fit items-center gap-2 text-sm font-medium text-accent transition-colors hover:brightness-110"
      >
        打开 API 文档 <ExternalLink size={14} />
      </a>
    </div>
  );
}