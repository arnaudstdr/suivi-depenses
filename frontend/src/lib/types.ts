export type AuthUser = {
  id: string;
  email: string;
  first_name: string;
  is_active: boolean;
};

export type Household = {
  id: string;
  name: string;
  currency: string;
  timezone: string;
};

export type HouseholdMember = {
  user_id: string;
  email: string;
  first_name: string;
  role: string;
  is_active: boolean;
};

export type AuthContext = {
  user: AuthUser;
  household: Household;
  role: string;
  members: HouseholdMember[];
};

export type Page<T> = {
  items: T[];
  total: number;
  limit: number;
  offset: number;
};

export type Category = {
  id: string;
  household_id: string | null;
  name: string;
  is_grocery: boolean;
  icon: string | null;
  is_active: boolean;
};

export type Transaction = {
  id: string;
  household_id: string | null;
  user_id: string;
  category_id: string;
  label: string;
  amount_cents: number;
  transaction_type: "expense" | "refund";
  scope: "personal" | "shared";
  budget_id: string | null;
  transaction_date: string;
  paid_at: string | null;
  status: string;
  notes: string | null;
};

export type DashboardDeductions = {
  personal_recurring_remaining_cents: number;
  personal_planned_remaining_cents: number;
  personal_transactions_remaining_cents: number;
  household_contribution_remaining_cents: number;
  household_contribution_status: string;
  total_cents: number;
};

export type DashboardResponse = {
  period: string;
  currency: string;
  personal_balance: {
    balance_cents: number;
    recorded_at: string;
  };
  deductions: DashboardDeductions;
  available_forecast_cents: number;
  grocery_budget: {
    allocated_cents: number;
    spent_cents: number;
    remaining_cents: number;
  };
  upcoming_recurring: {
    occurrence_id: string;
    recurring_expense_id: string;
    label: string;
    due_date: string;
    amount_cents: number;
    status: string;
  }[];
  recent_personal_transactions: {
    id: string;
    label: string;
    amount_cents: number;
    transaction_date: string;
    category_id: string;
    transaction_type: string;
  }[];
};

export type RecurringExpense = {
  id: string;
  household_id: string | null;
  owner_user_id: string;
  category_id: string;
  allocation_rule_id: string | null;
  label: string;
  amount_cents: number | null;
  scope: "personal" | "shared";
  frequency: string;
  start_date: string;
  end_date: string | null;
  due_day: number | null;
  amount_is_variable: boolean;
  is_active: boolean;
};

export type Contribution = {
  id: string;
  household_id: string;
  user_id: string;
  email: string;
  first_name: string;
  period: string;
  period_start: string;
  amount_cents: number;
  allocation_percentage: string;
  status: "pending" | "transferred" | "cancelled";
  transferred_at: string | null;
  transferred_amount_cents: number | null;
  transaction_id: string | null;
  created_at: string;
  updated_at: string;
};

export type AllocationRule = {
  id: string;
  name: string;
  is_default: boolean;
  members: {
    user_id: string;
    email: string;
    first_name: string;
    percentage: string;
  }[];
};

export type NotificationCount = {
  count: number;
};

export type ApiErrorBody = {
  code?: string;
  message?: string;
};
