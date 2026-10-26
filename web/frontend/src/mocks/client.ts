import type { Action, Health, Overview, User } from "@/lib/types";
import {
  MOCK_ACTIONS,
  MOCK_HEALTH,
  MOCK_OVERVIEW,
  MOCK_USERS,
} from "./data";

const latency = () => 300 + Math.random() * 300;

function delay<T>(data: T): Promise<T> {
  return new Promise((resolve) => setTimeout(() => resolve(data), latency()));
}

/** 数据访问契约：后续接入真实后端时保持同一份签名。 */
export interface ApiClient {
  getHealth(): Promise<Health>;
  getOverview(userId?: string): Promise<Overview>;
  getActions(): Promise<Action[]>;
  getUsers(): Promise<User[]>;
}

export const mockClient: ApiClient = {
  getHealth: () => delay(MOCK_HEALTH),
  getOverview: () => delay(MOCK_OVERVIEW),
  getActions: () => delay(MOCK_ACTIONS),
  getUsers: () => delay(MOCK_USERS),
};