import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { client, isMock } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { SaveError, User } from "@/lib/types";
import { useUser } from "@/providers/UserProvider";
import { useToast } from "@/providers/Toaster";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { ErrorBanner } from "@/components/ui/ErrorBanner";
import { Field } from "@/components/ui/Field";
import { Input } from "@/components/ui/Input";
import { Select } from "@/components/ui/Select";
import { Skeleton } from "@/components/ui/Skeleton";

const GRID =
  "grid grid-cols-[minmax(0,1.6fr)_64px_56px_104px_minmax(0,1fr)_76px] items-center gap-3";

function UserList({
  users,
  currentId,
  onSwitch,
}: {
  users: User[];
  currentId?: string;
  onSwitch: (id: string) => void;
}) {
  return (
    <div className="overflow-x-auto">
      <div className="min-w-[660px]">
        <div className={cn(GRID, "border-b border-line1 pb-2 text-xs uppercase tracking-[0.08em] text-text3")}>
          <span>用户</span>
          <span className="text-right">累计训练</span>
          <span className="text-right">今日</span>
          <span>创建时间</span>
          <span>徽章</span>
          <span />
        </div>
        {users.map((u) => {
          const isCurrent = u.id === currentId;
          return (
            <div key={u.id} className="relative border-b border-line1 last:border-0">
              {isCurrent && (
                <span className="absolute left-0 top-1/2 h-6 w-0.5 -translate-y-1/2 rounded-full bg-accent" />
              )}
              <div className={cn(GRID, "py-3 pl-3", isCurrent && "bg-surface2/40")}>
                <div className="flex min-w-0 items-center gap-2.5">
                  <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-surface2 text-xs text-text1">
                    {u.initials}
                  </div>
                  <span className="truncate text-sm text-text1">{u.name}</span>
                  {isCurrent && <Badge tone="accent">当前</Badge>}
                </div>
                <span className="text-right font-num text-text1">{u.total_sessions}</span>
                <span className="text-right font-num text-text1">{u.today_sessions}</span>
                <span className="font-mono text-text2">{u.created_at}</span>
                <span>
                  {u.badge ? <Badge tone="accent">{u.badge}</Badge> : <span className="text-text3">—</span>}
                </span>
                <div className="flex justify-end">
                  <Button
                    variant="secondary"
                    className="h-8 px-3 text-xs"
                    disabled={isCurrent}
                    onClick={() => onSwitch(u.id)}
                  >
                    切换
                  </Button>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export function ProfileSection() {
  const { users, usersLoading, usersError, refetchUsers, currentUser, activeUserId, switchUser } =
    useUser();
  const queryClient = useQueryClient();
  const toast = useToast();

  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [height, setHeight] = useState("");
  const [weight, setWeight] = useState("");
  const [createErrors, setCreateErrors] = useState<SaveError[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<User | null>(null);

  const createMutation = useMutation({
    mutationFn: client.createUser,
    onSuccess: async (res) => {
      if (res.ok) {
        // 先等 users 缓存带上新用户，再切换；否则 UserProvider 的
        // 「activeUserId 是否仍存在」校验会在旧缓存上把新用户打回 users[0]。
        await queryClient.invalidateQueries({ queryKey: ["users"] });
        if (res.user) switchUser(res.user.id);
        toast.push(`已创建并切换到「${res.user?.name}」`, "mint");
        setCreateOpen(false);
        setName("");
        setHeight("");
        setWeight("");
        setCreateErrors([]);
      } else {
        setCreateErrors(res.errors);
      }
    },
    onError: () => toast.push("创建失败，请重试", "coral"),
  });

  const deleteMutation = useMutation({
    mutationFn: client.deleteUser,
    onSuccess: (res) => {
      queryClient.invalidateQueries({ queryKey: ["users"] });
      if (res.ok) {
        toast.push(`已删除「${deleteTarget?.name}」`, "neutral");
      } else {
        toast.push(res.errors[0]?.message ?? "删除失败", "coral");
      }
      setDeleteTarget(null);
    },
    onError: () => toast.push("删除失败，请重试", "coral"),
  });

  function handleCreate() {
    const trimmed = name.trim();
    if (!trimmed) {
      setCreateErrors([{ field: "name", message: "用户名不能为空" }]);
      return;
    }
    setCreateErrors([]);
    const h = height === "" ? null : Number(height);
    const w = weight === "" ? null : Number(weight);
    createMutation.mutate({
      name: trimmed,
      height: h != null && Number.isFinite(h) ? h : null,
      weight: w != null && Number.isFinite(w) ? w : null,
    });
  }

  const nameError = createErrors.find((e) => e.field === "name")?.message;
  const generalError = createErrors.find((e) => !e.field)?.message;

  return (
    <div className="flex flex-col gap-6">
      {usersError && <ErrorBanner onRetry={() => refetchUsers()} />}

      <div className="grid grid-cols-12 gap-6">
        <Card className="col-span-12 lg:col-span-5" bodyClassName="flex h-full flex-col">
          {usersLoading || !currentUser ? (
            <div className="space-y-3">
              <Skeleton className="h-14 w-14 rounded-2xl" />
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-4 w-56" />
              <Skeleton className="mt-4 h-24" />
            </div>
          ) : (
            <>
              <div className="flex items-center gap-4">
                <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-surface2 text-xl text-text1">
                  {currentUser.initials}
                </div>
                <div>
                  <h3 className="text-lg font-medium text-text1">{currentUser.name}</h3>
                  <p className="text-sm text-text3">创建于 {currentUser.created_at}</p>
                </div>
              </div>

              <dl className="mt-5 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-xs uppercase tracking-[0.12em] text-text3">身高</dt>
                  <dd className="mt-1 text-text1">
                    {currentUser.height != null ? `${currentUser.height} cm` : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[0.12em] text-text3">体重</dt>
                  <dd className="mt-1 text-text1">
                    {currentUser.weight != null ? `${currentUser.weight} kg` : "—"}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[0.12em] text-text3">累计训练</dt>
                  <dd className="mt-1 font-num text-text1">{currentUser.total_sessions}</dd>
                </div>
                <div>
                  <dt className="text-xs uppercase tracking-[0.12em] text-text3">今日</dt>
                  <dd className="mt-1 font-num text-text1">{currentUser.today_sessions}</dd>
                </div>
              </dl>

              <div className="mt-auto flex items-center gap-2 pt-6">
                <Select
                  value={activeUserId ?? ""}
                  onChange={(e) => switchUser(e.target.value)}
                  className="flex-1"
                >
                  {users?.map((u) => (
                    <option key={u.id} value={u.id}>
                      {u.name}
                    </option>
                  ))}
                </Select>
                <Button variant="primary" onClick={() => setCreateOpen(true)}>
                  <Plus size={15} /> 新建用户
                </Button>
              </div>
            </>
          )}
        </Card>

        <Card
          className="col-span-12 lg:col-span-7"
          title="用户列表"
          subtitle={isMock ? "Mock 模式下新建用户仅本次会话有效。" : "新建用户会保存到 data/users/，刷新后仍在。"}
        >
          {usersLoading ? (
            <div className="space-y-3">
              <Skeleton className="h-12" />
              <Skeleton className="h-12" />
            </div>
          ) : !users || users.length === 0 ? (
            <p className="text-sm text-text3">暂无用户。</p>
          ) : (
            <UserList users={users} currentId={activeUserId} onSwitch={switchUser} />
          )}
        </Card>
      </div>

      <Card className="border-coral/30" title="删除用户" subtitle="危险操作，删除后不可恢复">
        {usersLoading ? (
          <Skeleton className="h-12" />
        ) : users && users.length <= 1 ? (
          <p className="text-sm text-text3">只剩一个用户，无法删除。</p>
        ) : (
          <div className="divide-y divide-line1">
            {users?.map((u) => (
              <div
                key={u.id}
                className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0"
              >
                <div className="flex items-center gap-2.5">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-surface2 text-xs text-text1">
                    {u.initials}
                  </div>
                  <span className="text-sm text-text1">{u.name}</span>
                  {u.id === activeUserId && <Badge tone="accent">当前</Badge>}
                </div>
                <Button
                  variant="ghost"
                  className="text-coral hover:bg-coral/10 hover:text-coral"
                  onClick={() => setDeleteTarget(u)}
                >
                  <Trash2 size={15} /> 删除
                </Button>
              </div>
            ))}
          </div>
        )}
      </Card>

      <p className="text-xs text-text3">
        数据保存在 data/users/&lt;用户名&gt;/，视频帧不落盘。
      </p>

      <Dialog
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        title="新建用户"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setCreateOpen(false)}
              disabled={createMutation.isPending}
            >
              取消
            </Button>
            <Button
              variant="primary"
              onClick={handleCreate}
              disabled={createMutation.isPending}
            >
              {createMutation.isPending ? "处理中…" : "创建并切换"}
            </Button>
          </>
        }
      >
        <div className="flex flex-col gap-4">
          {generalError && <p className="text-xs text-coral">{generalError}</p>}
          <Field label="用户名" required error={nameError}>
            <Input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="例如：张三"
              autoFocus
            />
          </Field>
          <div className="grid grid-cols-2 gap-4">
            <Field label="身高 cm" help="可选">
              <Input
                type="number"
                min={0}
                inputMode="numeric"
                value={height}
                onChange={(e) => setHeight(e.target.value)}
                placeholder="175"
              />
            </Field>
            <Field label="体重 kg" help="可选">
              <Input
                type="number"
                min={0}
                inputMode="numeric"
                value={weight}
                onChange={(e) => setWeight(e.target.value)}
                placeholder="65"
              />
            </Field>
          </div>
          <p className="text-xs text-text3">{isMock ? "Mock 模式下仅本次会话有效，刷新后恢复初始用户。" : "保存后写入 data/users/<用户名>/，刷新不会丢。"}</p>
        </div>
      </Dialog>

      <Dialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="删除用户"
        footer={
          <>
            <Button
              variant="secondary"
              onClick={() => setDeleteTarget(null)}
              disabled={deleteMutation.isPending}
            >
              取消
            </Button>
            <Button
              variant="danger"
              onClick={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
              disabled={deleteMutation.isPending}
            >
              {deleteMutation.isPending ? "处理中…" : "确认删除"}
            </Button>
          </>
        }
      >
        <p className="text-sm text-text1">
          将删除用户「{deleteTarget?.name}」的档案、历史、目标，{" "}
          <span className="text-coral">不可恢复</span>。
        </p>
      </Dialog>
    </div>
  );
}