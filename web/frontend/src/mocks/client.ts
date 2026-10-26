import type {
  Action,
  ActionDetail,
  ActionValidationResult,
  Health,
  Overview,
  User,
} from "@/lib/types";
import {
  MOCK_ACTIONS,
  MOCK_ACTION_DETAILS,
  MOCK_HEALTH,
  MOCK_OVERVIEW,
  MOCK_USERS,
  MOCK_VALIDATION_RESULTS,
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
  getAction(id: string): Promise<ActionDetail | null>;
  validateActions(): Promise<ActionValidationResult[]>;
  getUsers(): Promise<User[]>;
}

export const mockClient: ApiClient = {
  getHealth: () => delay(MOCK_HEALTH),
  getOverview: () => delay(MOCK_OVERVIEW),
  getActions: () => delay(MOCK_ACTIONS),
  getAction: (id) =>
    delay(MOCK_ACTION_DETAILS.find((d) => d.id === id) ?? null),
  validateActions: () => delay(MOCK_VALIDATION_RESULTS),
  getUsers: () => delay(MOCK_USERS),
};