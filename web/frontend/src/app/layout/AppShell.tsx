import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { NAV_ITEMS } from "@/app/nav";
import { cn } from "@/lib/cn";
import { useUser } from "@/providers/UserProvider";
import { Sidebar } from "./Sidebar";
import { TopBar } from "./TopBar";

function MobileTabBar() {
  return (
    <nav className="fixed inset-x-0 bottom-0 z-30 flex border-t border-line1 bg-bg1 lg:hidden">
      {NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        return (
          <NavLink
            key={item.key}
            to={item.path}
            end={item.path === "/"}
            className="flex flex-1 flex-col items-center gap-0.5 py-2.5"
          >
            {({ isActive }) => (
              <>
                <Icon
                  size={18}
                  className={isActive ? "text-accent" : "text-text3"}
                />
                <span
                  className={cn(
                    "text-[11px]",
                    isActive ? "text-accent" : "text-text3",
                  )}
                >
                  {item.label}
                </span>
              </>
            )}
          </NavLink>
        );
      })}
    </nav>
  );
}

export function AppShell() {
  const [collapsed, setCollapsed] = useState(false);
  const { currentUser: user, users, switchUser } = useUser();

  return (
    <div className="flex h-screen overflow-hidden bg-bg0">
      <Sidebar user={user} collapsed={collapsed} />

      <div className="flex min-w-0 flex-1 flex-col">
        <TopBar
          collapsed={collapsed}
          onToggle={() => setCollapsed((c) => !c)}
          user={user}
          users={users}
          onSelectUser={switchUser}
        />

        <main className="flex-1 overflow-y-auto px-4 py-6 pb-24 md:px-8 md:py-8 lg:pb-8">
          <div className="mx-auto max-w-[1600px] animate-fade-in-up">
            <Outlet />
          </div>
        </main>
      </div>

      <MobileTabBar />
    </div>
  );
}