import type { ApiClient } from "@/mocks/client";
import { mockClient } from "@/mocks/client";

// 本轮数据层为 mock；接入真实后端时把 client 换成 HTTP 实现即可，组件不变。
export const isMock = import.meta.env.VITE_USE_MOCK !== "false";

export const client: ApiClient = mockClient;