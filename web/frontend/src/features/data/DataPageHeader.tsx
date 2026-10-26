import { Download } from "lucide-react";
import { Button } from "@/components/ui/Button";

export function DataPageHeader({
  userName,
  exporting,
  onExport,
}: {
  userName?: string;
  exporting: boolean;
  onExport: () => void;
}) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-2xl font-medium text-text1">训练数据</h1>
        <p className="mt-1 text-sm text-text3">
          当前用户：{userName ?? "加载中…"} · 按动作与时间范围查看历史
        </p>
      </div>
      <Button variant="secondary" onClick={onExport} disabled={exporting}>
        <Download size={15} />
        {exporting ? "导出中…" : "导出 CSV"}
      </Button>
    </div>
  );
}
