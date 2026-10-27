import type { ApiClient } from "@/mocks/client";
import { mockClient } from "@/mocks/client";
import type {
  Health,
  HistoryQuery,
  HistoryResult,
  Overview,
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
 * 目前「动作库」的几个接口仍然复用 mock —— 动作列表/详情是静态展示数据，
 * 后台还没有对应的 REST（`configs/*.json` 的展示字段需要翻译层），
 * 等那部分接好再把 getActions 系列切过来。数据类接口（用户 / 总览 / 历史 / 目标 / 健康）
 * 已经全部走真实后端，训练记录能看到、能写进 `data/users/<用户名>/`。
 */
export const httpClient: ApiClient = {
  getHealth: () => request<Health>("/api/health"),

  getOverview: (userId, days = 14) =>
    request<Overview>(`/api/overview${qs({ user: userId, days })}`),

  getActions: () => mockClient.getActions(),
  getAction: (id) => mockClient.getAction(id),
  validateActions: () => mockClient.validateActions(),
  createAction: (draft) => mockClient.createAction(draft),

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
