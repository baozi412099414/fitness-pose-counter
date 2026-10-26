import type {
  Action,
  ActionDetail,
  ActionValidationResult,
  CreateUserInput,
  Health,
  NewActionDraft,
  Overview,
  SaveError,
  SaveResult,
  User,
  UserOpResult,
} from "@/lib/types";
import {
  clearGoal as clearGoalFn,
  createAction as saveAction,
  createUser as createUserFn,
  deleteUser as deleteUserFn,
  getActionSummaries,
  getOverviewData,
  getUsersSnapshot,
  getValidationResults,
  MOCK_ACTION_DETAILS,
  MOCK_HEALTH,
  setGoal as setGoalFn,
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
  createUser(input: CreateUserInput): Promise<UserOpResult>;
  deleteUser(id: string): Promise<{ ok: boolean; errors: SaveError[] }>;
  setGoal(actionId: string, target: number): Promise<void>;
  clearGoal(actionId: string): Promise<void>;
}

export const mockClient: ApiClient = {
  getHealth: () => delay(MOCK_HEALTH),
  getOverview: () => delay(getOverviewData()),
  getActions: () => delay(getActionSummaries()),
  getAction: (id) =>
    delay(MOCK_ACTION_DETAILS.find((d) => d.id === id) ?? null),
  validateActions: () => delay(getValidationResults()),
  getUsers: () => delay(getUsersSnapshot()),
  createAction: (draft) => delay(saveAction(draft)),
  createUser: (input) => delay(createUserFn(input)),
  deleteUser: (id) => delay(deleteUserFn(id)),
  setGoal: (actionId, target) => delay(setGoalFn(actionId, target)),
  clearGoal: (actionId) => delay(clearGoalFn(actionId)),
};