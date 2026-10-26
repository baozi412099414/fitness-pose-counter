import { EmptyState } from "@/components/ui/EmptyState";

export function PlaceholderPage({ title }: { title: string }) {
  return (
    <div>
      <h1 className="text-2xl font-medium text-text1">{title}</h1>
      <div className="mt-6">
        <EmptyState
          title="该页面尚未实现"
          description="将在后续阶段接入：实时训练、动作库、数据看板与设置。"
        />
      </div>
    </div>
  );
}