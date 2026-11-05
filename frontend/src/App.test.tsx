// @vitest-environment jsdom

import "@testing-library/jest-dom/vitest";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import App from "./App";

const authContext = {
  user: {
    id: "user-1",
    email: "owner@example.com",
    first_name: "Alice",
    is_active: true,
  },
  household: {
    id: "household-1",
    name: "Foyer test",
    currency: "EUR",
    timezone: "Europe/Paris",
  },
  role: "owner",
  members: [
    {
      user_id: "user-1",
      email: "owner@example.com",
      first_name: "Alice",
      role: "owner",
      is_active: true,
    },
    {
      user_id: "user-2",
      email: "member@example.com",
      first_name: "Bob",
      role: "member",
      is_active: true,
    },
  ],
};

const dashboard = {
  period: "2026-11",
  currency: "EUR",
  personal_balance: {
    balance_cents: 150000,
    recorded_at: "2026-11-05T09:30:00Z",
  },
  deductions: {
    personal_recurring_remaining_cents: 8818,
    personal_planned_remaining_cents: 10750,
    personal_transactions_remaining_cents: 0,
    household_contribution_remaining_cents: 30000,
    household_contribution_status: "pending",
    total_cents: 49568,
  },
  available_forecast_cents: 100432,
  grocery_budget: {
    allocated_cents: 49000,
    spent_cents: 20580,
    remaining_cents: 28420,
  },
  upcoming_recurring: [
    {
      occurrence_id: "occurrence-1",
      recurring_expense_id: "recurring-1",
      label: "Téléphone",
      due_date: "2026-11-08",
      amount_cents: 1999,
      status: "pending",
    },
  ],
  recent_personal_transactions: [
    {
      id: "transaction-1",
      label: "Carburant",
      amount_cents: 4200,
      transaction_date: "2026-11-04",
      category_id: "category-transport",
      transaction_type: "expense",
    },
  ],
};

const categories = [
  {
    id: "category-transport",
    household_id: null,
    name: "Transport",
    is_grocery: false,
    icon: "car",
    is_active: true,
  },
  {
    id: "category-grocery",
    household_id: null,
    name: "Courses / alimentation",
    is_grocery: true,
    icon: "basket",
    is_active: true,
  },
];

const transaction = {
  id: "transaction-1",
  household_id: null,
  user_id: "user-1",
  category_id: "category-transport",
  label: "Carburant",
  amount_cents: 4200,
  transaction_type: "expense",
  scope: "personal",
  budget_id: null,
  transaction_date: "2026-11-04",
  paid_at: "2026-11-04T12:00:00Z",
  status: "paid",
  notes: null,
};

const contribution = {
  id: "contribution-1",
  household_id: "household-1",
  user_id: "user-1",
  email: "owner@example.com",
  first_name: "Alice",
  period: "2026-11",
  period_start: "2026-11-01",
  amount_cents: 30000,
  allocation_percentage: "55.000",
  status: "pending",
  transferred_at: null,
  transferred_amount_cents: null,
  transaction_id: null,
  created_at: "2026-11-01T00:00:00Z",
  updated_at: "2026-11-01T00:00:00Z",
};

function json(data: unknown, status = 200): Promise<Response> {
  return Promise.resolve(
    new Response(JSON.stringify(data), {
      status,
      headers: { "content-type": "application/json" },
    }),
  );
}

describe("App", () => {
  let authenticated = false;

  beforeEach(() => {
    authenticated = false;
    window.localStorage.clear();
    vi.stubGlobal(
      "fetch",
      vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
        const url = typeof input === "string" ? input : input.toString();
        if (
          url.includes("/api/v1/households/me/allocation-rules/default") &&
          init?.method === "PUT"
        ) {
          return json({
            id: "rule-1",
            name: "Répartition par défaut",
            is_default: true,
            members: [
              {
                user_id: "user-1",
                email: "owner@example.com",
                first_name: "Alice",
                percentage: "60.000",
              },
              {
                user_id: "user-2",
                email: "member@example.com",
                first_name: "Bob",
                percentage: "40.000",
              },
            ],
          });
        }
        if (
          url.includes("/api/v1/recurring-expenses") &&
          init?.method === "POST"
        ) {
          return json(
            {
              id: "recurring-created",
              household_id: null,
              owner_user_id: "user-1",
              category_id: "category-transport",
              allocation_rule_id: null,
              label: "Assurance auto",
              amount_cents: 1999,
              scope: "personal",
              frequency: "monthly",
              start_date: "2026-11-05",
              end_date: null,
              due_day: 5,
              amount_is_variable: false,
              is_active: true,
            },
            201,
          );
        }
        if (url.includes("/api/v1/auth/csrf")) {
          return json({ csrf_token: "csrf-token" });
        }
        if (url.includes("/api/v1/auth/login")) {
          authenticated = true;
          return json(authContext);
        }
        if (url.includes("/api/v1/auth/logout")) {
          authenticated = false;
          return Promise.resolve(new Response(null, { status: 204 }));
        }
        if (url.includes("/api/v1/auth/me")) {
          return authenticated
            ? json(authContext)
            : json({ code: "unauthorized", message: "Non authentifié." }, 401);
        }
        if (url.includes("/api/v1/users/me/dashboard")) {
          return json(dashboard);
        }
        if (url.includes("/api/v1/categories")) {
          return json(categories);
        }
        if (url.includes("/api/v1/transactions")) {
          return json({
            items: [transaction],
            total: 1,
            limit: 50,
            offset: 0,
          });
        }
        if (url.includes("/api/v1/households/me/contributions")) {
          return json([contribution]);
        }
        if (url.includes("/api/v1/recurring-expenses")) {
          return json({
            items: [
              {
                id: "recurring-1",
                household_id: null,
                owner_user_id: "user-1",
                category_id: "category-transport",
                allocation_rule_id: null,
                label: "Téléphone",
                amount_cents: 1999,
                scope: "personal",
                frequency: "monthly",
                start_date: "2025-01-08",
                end_date: null,
                due_day: 8,
                amount_is_variable: false,
                is_active: true,
              },
            ],
            total: 1,
            limit: 100,
            offset: 0,
          });
        }
        if (url.includes("/api/v1/notifications/unread-count")) {
          return json({ count: 1 });
        }
        if (url.includes("/api/v1/households/me/allocation-rules")) {
          return json([
            {
              id: "rule-1",
              name: "Répartition par défaut",
              is_default: true,
              members: [
                {
                  user_id: "user-1",
                  email: "owner@example.com",
                  first_name: "Alice",
                  percentage: "55.000",
                },
                {
                  user_id: "user-2",
                  email: "member@example.com",
                  first_name: "Bob",
                  percentage: "45.000",
                },
              ],
            },
          ]);
        }
        return json({ code: "not_found", message: url }, 404);
      }),
    );
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("connecte l'utilisateur et affiche le dashboard réel", async () => {
    const user = userEvent.setup();
    render(<App />);

    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeVisible();
    await user.type(screen.getByLabelText("Adresse email"), "owner@example.com");
    await user.type(screen.getByLabelText("Mot de passe"), "secret-password");
    await user.click(screen.getByRole("button", { name: /Se connecter/i }));

    expect(
      await screen.findByRole("heading", { name: "Mon budget personnel" }),
    ).toBeVisible();
    expect(screen.getByText("Participation au foyer")).toBeVisible();
    expect(screen.getByText("Téléphone")).toBeVisible();
    expect(screen.getByText("Carburant")).toBeVisible();
    expect(screen.getByText("Alice")).toBeVisible();
  });

  it("permet de créer une charge récurrente", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(
      await screen.findByLabelText("Adresse email"),
      "owner@example.com",
    );
    await user.type(screen.getByLabelText("Mot de passe"), "secret-password");
    await user.click(screen.getByRole("button", { name: /Se connecter/i }));
    await screen.findByRole("heading", { name: "Mon budget personnel" });

    await user.click(
      screen.getByRole("button", { name: "Charges récurrentes" }),
    );
    await user.click(
      await screen.findByRole("button", { name: /Ajouter une charge/i }),
    );
    expect(
      await screen.findByRole("heading", {
        name: "Nouvelle charge récurrente",
      }),
    ).toBeVisible();

    await user.type(screen.getByLabelText("Libellé"), "Assurance auto");
    await user.type(screen.getByLabelText("Montant (€)"), "19.99");
    await user.click(screen.getByRole("button", { name: /Créer la charge/i }));

    expect(
      vi.mocked(fetch).mock.calls.some(
        ([url, init]) =>
          String(url).includes("/api/v1/recurring-expenses") &&
          init?.method === "POST",
      ),
    ).toBe(true);
  });

  it("permet de modifier la répartition par défaut", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(
      await screen.findByLabelText("Adresse email"),
      "owner@example.com",
    );
    await user.type(screen.getByLabelText("Mot de passe"), "secret-password");
    await user.click(screen.getByRole("button", { name: /Se connecter/i }));
    await screen.findByRole("heading", { name: "Mon budget personnel" });

    await user.click(screen.getByRole("button", { name: "Répartition" }));

    const alice = await screen.findByLabelText("Pourcentage de Alice");
    await user.clear(alice);
    await user.type(alice, "60");
    const bob = screen.getByLabelText("Pourcentage de Bob");
    await user.clear(bob);
    await user.type(bob, "40");
    await user.click(
      screen.getByRole("button", { name: /Enregistrer la répartition/i }),
    );

    expect(
      vi.mocked(fetch).mock.calls.some(
        ([url, init]) =>
          String(url).includes(
            "/api/v1/households/me/allocation-rules/default",
          ) && init?.method === "PUT",
      ),
    ).toBe(true);
  });

  it("passe en lecture seule hors ligne", async () => {
    const user = userEvent.setup();
    render(<App />);
    await user.type(
      await screen.findByLabelText("Adresse email"),
      "owner@example.com",
    );
    await user.type(screen.getByLabelText("Mot de passe"), "secret-password");
    await user.click(screen.getByRole("button", { name: /Se connecter/i }));
    await screen.findByRole("heading", { name: "Mon budget personnel" });

    Object.defineProperty(navigator, "onLine", {
      configurable: true,
      value: false,
    });
    window.dispatchEvent(new Event("offline"));

    expect(await screen.findByText(/Hors ligne/)).toBeVisible();
    expect(
      screen.getByRole("button", { name: /Ajouter une dépense/i }),
    ).toBeDisabled();
    expect(
      screen.getByRole("button", { name: /Modifier le solde/i }),
    ).toBeDisabled();
  });
});
