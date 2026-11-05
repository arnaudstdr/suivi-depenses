import { useCallback, useEffect, useState } from "react";

import { ApiError, apiRequest } from "../lib/api";
import { getLastSyncedAt, markSynced } from "../lib/session";
import type {
  AllocationRule,
  Category,
  Contribution,
  DashboardResponse,
  NotificationCount,
  Page,
  RecurringExpense,
  Transaction,
} from "../lib/types";

export type DashboardData = {
  dashboard: DashboardResponse | null;
  categories: Category[];
  transactions: Transaction[];
  contributions: Contribution[];
  recurring: RecurringExpense[];
  allocationRules: AllocationRule[];
  unreadCount: number;
  fromCache: boolean;
  lastSyncedAt: string | null;
};

export type DashboardDataState = {
  data: DashboardData;
  loading: boolean;
  error: string | null;
  needsBalance: boolean;
  refresh: () => Promise<void>;
};

const EMPTY_DATA: DashboardData = {
  dashboard: null,
  categories: [],
  transactions: [],
  contributions: [],
  recurring: [],
  allocationRules: [],
  unreadCount: 0,
  fromCache: false,
  lastSyncedAt: null,
};

export function useDashboardData(
  userId: string,
  online: boolean,
): DashboardDataState {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [needsBalance, setNeedsBalance] = useState(false);

  const refresh = useCallback(async () => {
    setLoading(true);
    setError(null);
    const cacheUserId = userId;
    const results = await Promise.allSettled([
      apiRequest<DashboardResponse>("/api/v1/users/me/dashboard", {
        cacheUserId,
      }),
      apiRequest<Category[]>("/api/v1/categories", { cacheUserId }),
      apiRequest<Page<Transaction>>("/api/v1/transactions?limit=50", {
        cacheUserId,
      }),
      apiRequest<Contribution[]>("/api/v1/households/me/contributions", {
        cacheUserId,
      }),
      apiRequest<Page<RecurringExpense>>("/api/v1/recurring-expenses?limit=100", {
        cacheUserId,
      }),
      apiRequest<NotificationCount>("/api/v1/notifications/unread-count", {
        cacheUserId,
      }),
      apiRequest<AllocationRule[]>(
        "/api/v1/households/me/allocation-rules",
        { cacheUserId },
      ),
    ]);

    const dashboardResult = results[0];
    let balanceRequired = false;
    if (dashboardResult.status === "rejected") {
      const reason = dashboardResult.reason;
      if (reason instanceof ApiError && reason.code === "balance_required") {
        balanceRequired = true;
      } else {
        setError(
          reason instanceof Error
            ? reason.message
            : "Impossible de charger le tableau de bord.",
        );
      }
    } else if (dashboardResult.value.fromCache && !online) {
      setError(null);
    }

    const anyFresh = results.some(
      (result) => result.status === "fulfilled" && !result.value.fromCache,
    );
    if (anyFresh) {
      markSynced();
    }

    const next: DashboardData = {
      dashboard:
        results[0].status === "fulfilled" ? results[0].value.data : null,
      categories:
        results[1].status === "fulfilled" ? results[1].value.data : [],
      transactions:
        results[2].status === "fulfilled"
          ? results[2].value.data.items
          : [],
      contributions:
        results[3].status === "fulfilled" ? results[3].value.data : [],
      recurring:
        results[4].status === "fulfilled"
          ? results[4].value.data.items
          : [],
      unreadCount:
        results[5].status === "fulfilled" ? results[5].value.data.count : 0,
      allocationRules:
        results[6].status === "fulfilled" ? results[6].value.data : [],
      fromCache: results.some(
        (result) => result.status === "fulfilled" && result.value.fromCache,
      ),
      lastSyncedAt: getLastSyncedAt(),
    };

    setData(next);
    setNeedsBalance(balanceRequired);
    setLoading(false);
  }, [online, userId]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { data: data ?? EMPTY_DATA, loading, error, needsBalance, refresh };
}
