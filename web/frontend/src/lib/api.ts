import type { ApiClient } from "@/mocks/client";
import { mockClient } from "@/mocks/client";
import { httpClient } from "./httpClient";

/**
 * 数据层开关。
 *
 * 默认**走真实后端**（`web/backend`，训练记录落在 `data/users/<用户名>/`）；
 * 想只看界面、不启动 Python 时，建一个 `.env.local` 写 `VITE_USE_MOCK=true`。
 */
export const isMock = import.meta.env.VITE_USE_MOCK === "true";

export const client: ApiClient = isMock ? mockClient : httpClient;
