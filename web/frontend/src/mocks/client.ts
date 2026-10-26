import type {
  Action,
  ActionDetail,
  ActionValidationResult,
  Health,
  NewActionDraft,
  Overview,
  SaveResult,
  User,
} from "@/lib/types";
import {
  createAction as saveAction,
  getActionSummaries,
  getValidationResults,
  MOCK_ACTION_DETAILS,
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
  getAction(id: string): Promise<ActionDetail | null>;
  validateActions(): Promise<ActionValidationResult[]>;
  getUsers(): Promise<User[]>;
  createAction(draft: NewActionDraft): Promise<SaveResult>;
}

export const mockClient: ApiClient = {
  getHealth: () => delay(MOCK_HEALTH),
  getOverview: () => delay(MOCK_OVERVIEW),
  getActions: () => delay(getActionSummaries()),
  getAction: (id) =>
    delay(MOCK_ACTION_DETAILS.find((d) => d.id === id) ?? null),
  validateActions: () => delay(getValidationResults()),
  getUsers: () => delay(MOCK_USERS),
  createAction: (draft) => delay(saveAction(draft)),
};