import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useQuery } from "@tanstack/react-query";
import { client } from "@/lib/api";
import type { User } from "@/lib/types";

const STORAGE_KEY = "formlab.activeUserId";

interface UserContextValue {
  users?: User[];
  usersLoading: boolean;
  usersError: Error | null;
  refetchUsers: () => void;
  currentUser?: User;
  activeUserId?: string;
  switchUser: (id: string) => void;
  clearActiveUser: () => void;
}

const UserContext = createContext<UserContextValue | null>(null);

export function useUser(): UserContextValue {
  const ctx = useContext(UserContext);
  if (!ctx) {
    throw new Error("useUser 必须在 <UserProvider> 内使用");
  }
  return ctx;
}

export function UserProvider({ children }: { children: ReactNode }) {
  const {
    data: users,
    isLoading,
    error,
    refetch,
  } = useQuery({
    queryKey: ["users"],
    queryFn: client.getUsers,
  });

  const [activeUserId, setActiveUserId] = useState<string | undefined>(() => {
    try {
      return localStorage.getItem(STORAGE_KEY) ?? undefined;
    } catch {
      return undefined;
    }
  });

  // users 加载完成后校验 activeUserId；失效（不存在/已删除）则回退 users[0] 并清理。
  useEffect(() => {
    if (!users || users.length === 0) return;
    if (!activeUserId || !users.some((u) => u.id === activeUserId)) {
      setActiveUserId(users[0].id);
      try {
        localStorage.removeItem(STORAGE_KEY);
      } catch {
        /* ignore */
      }
    }
  }, [users, activeUserId]);

  const switchUser = useCallback((id: string) => {
    setActiveUserId(id);
    try {
      localStorage.setItem(STORAGE_KEY, id);
    } catch {
      /* ignore */
    }
  }, []);

  const clearActiveUser = useCallback(() => {
    setActiveUserId(undefined);
    try {
      localStorage.removeItem(STORAGE_KEY);
    } catch {
      /* ignore */
    }
  }, []);

  const currentUser =
    users?.find((u) => u.id === activeUserId) ?? users?.[0];

  return (
    <UserContext.Provider
      value={{
        users,
        usersLoading: isLoading,
        usersError: error,
        refetchUsers: refetch,
        currentUser,
        activeUserId,
        switchUser,
        clearActiveUser,
      }}
    >
      {children}
    </UserContext.Provider>
  );
}