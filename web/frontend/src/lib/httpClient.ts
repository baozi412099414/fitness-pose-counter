import type { ApiClient } from "@/mocks/client";
import type {
  Action,
  ActionDetail,
  ActionValidationResult,
  Health,
  HistoryQuery,
  HistoryResult,
  NewActionDraft,
  Overview,
  SaveResult,
  User,
  UserOpResult,
} from "@/lib/types";

/** 空字符串 = 同源，靠 Vite 的 /api 代理转到 127.0.0.1:8000 */
const BASE = "";

function qs(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  }
  const text = search.toString();
  return text ? `?${text}` : "";
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new Error("连不上判定服务（127.0.0.1:8000），先启动后端或改用 mock");
  }
  if (!response.ok) {
    let detail = `请求失败：HTTP ${response.status}`;
    try {
      const body = (await response.json()) as { detail?: unknown };
      if (typeof body.detail === "string") detail = body.detail;
    } catch {
      /* 响应不是 JSON，保留默认文案 */
    }
    throw new Error(detail);
  }
  return (await response.json()) as T;
}

/**
 * 真实后端的实现。
 *
 * 所有接口都走 `web/backend`：用户 / 总览 / 历史 / 目标 / 健康，
 * 以及动作库（列表、详情、校验、新建、删除）—— 新建动作就是往 `configs/` 写一份 JSON。
 */
export const httpClient: ApiClient = {
  getHealth: () => request<Health>("/api/health"),

  getOverview: (userId, days = 14) =>
    request<Overview>(`/api/overview${qs({ user: userId, days })}`),

  getActions: async () => {
    const data = await request<{ items: Action[] }>("/api/actions");
    return data.items;
  },

  getAction: async (id) => {
    try {
      return await request<ActionDetail>(`/api/actions/${encodeURIComponent(id)}`);
    } catch {
      return null; // 404 = 动作不存在，交给页面显示空态
    }
  },

  validateActions: async () => {
    const data = await request<{ items: ActionValidationResult[] }>(
      "/api/actions/validate",
      { method: "POST", body: "{}" },
    );
    return data.items;
  },

  createAction: (draft: NewActionDraft) =>
    request<SaveResult>("/api/actions", {
      method: "POST",
      body: JSON.stringify(draft),
    }),

  deleteAction: (id: string) =>
    request<{ ok: boolean; errors: { message: string }[] }>(
      `/api/actions/${encodeURIComponent(id)}`,
      { method: "DELETE" },
    ),

  getUsers: () => request<User[]>("/api/users"),

  createUser: (input) =>
    request<UserOpResult>("/api/users", {
      method: "POST",
      body: JSON.stringify({
        name: input.name,
        height: input.height ?? null,
        weight: input.weight ?? null,
      }),
    }),

  deleteUser: (id) =>
    request<{ ok: boolean; errors: { message: string }[] }>(
      `/api/users/${encodeURIComponent(id)}`,
      { method: "DELETE" },
    ),

  getHistory: (q: HistoryQuery) =>
    request<HistoryResult>(
      `/api/history${qs({
        user: q.userId,
        action: q.actionId,
        limit: q.limit,
        offset: q.offset,
      })}`,
    ),

  setGoal: async (userId, actionId, target) => {
    await request(`/api/goals/${encodeURIComponent(actionId)}${qs({ user: userId })}`, {
      method: "PUT",
      body: JSON.stringify({ target }),
    });
  },

  clearGoal: async (userId, actionId) => {
    await request(`/api/goals/${encodeURIComponent(actionId)}${qs({ user: userId })}`, {
      method: "DELETE",
    });
  },
};
