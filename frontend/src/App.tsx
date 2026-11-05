import { FormEvent, ReactNode, useEffect, useMemo, useState } from "react";
import type { LucideIcon } from "lucide-react";
import {
  Wallet,
  LayoutDashboard,
  ArrowLeftRight,
  Repeat2,
  Scale,
  History,
  Settings,
  Bell,
  Plus,
  ChevronDown,
  CalendarDays,
  Menu,
  X,
  ShoppingBasket,
  House,
  Car,
  HeartPulse,
  Coffee,
  ArrowUpRight,
  ArrowDownRight,
  Pencil,
  Check,
  CircleHelp,
  LogOut,
  WifiOff,
  RefreshCw,
  LoaderCircle,
} from "lucide-react";

import { LoginScreen } from "./features/auth/LoginScreen";
import { useDashboardData } from "./hooks/useDashboardData";
import { useSession } from "./hooks/useSession";
import { api } from "./lib/api";
import type {
  AuthContext,
  Category,
  Contribution,
  Transaction,
} from "./lib/types";

type Context = "Personnel" | "Foyer";
type Section =
  | "Vue d'ensemble"
  | "Dépenses"
  | "Charges récurrentes"
  | "Budget courses"
  | "Répartition"
  | "Historique";
type Scope = "personal" | "shared";

type RecurringTarget = {
  occurrenceId: string;
  label: string;
  amountCents: number;
  amountIsVariable: boolean;
  dueDate: string;
};

type RecurringForm = {
  label: string;
  amount: string;
  categoryId: string;
  scope: Scope;
  frequency: "weekly" | "monthly" | "quarterly" | "semiannual" | "yearly";
  startDate: string;
  endDate: string;
  dueDay: string;
  amountIsVariable: boolean;
};

const nav = [
  { label: "Vue d'ensemble" as Section, icon: LayoutDashboard },
  { label: "Dépenses" as Section, icon: ArrowLeftRight },
  { label: "Charges récurrentes" as Section, icon: Repeat2 },
  { label: "Budget courses" as Section, icon: ShoppingBasket },
  { label: "Répartition" as Section, icon: Scale },
  { label: "Historique" as Section, icon: History },
];

function App() {
  const session = useSession();

  if (session.loading && session.context === null) {
    return <SplashScreen />;
  }
  if (session.context === null) {
    return (
      <LoginScreen
        online={session.online}
        error={session.error}
        onSubmit={session.login}
      />
    );
  }
  return (
    <Dashboard
      session={session.context}
      online={session.online}
      onLogout={session.logout}
    />
  );
}

function Dashboard({
  session,
  online,
  onLogout,
}: {
  session: AuthContext;
  online: boolean;
  onLogout: () => Promise<void>;
}) {
  const { data, loading, error, needsBalance, refresh } = useDashboardData(
    session.user.id,
    online,
  );
  const [context, setContext] = useState<Context>("Personnel");
  const [section, setSection] = useState<Section>("Vue d'ensemble");
  const [mobileMenu, setMobileMenu] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const [showBalance, setShowBalance] = useState(false);
  const [showContribution, setShowContribution] = useState(false);
  const [showRecurring, setShowRecurring] = useState(false);
  const [showAddRecurring, setShowAddRecurring] = useState(false);
  const [selectedRecurring, setSelectedRecurring] =
    useState<RecurringTarget | null>(null);
  const [form, setForm] = useState({
    label: "",
    amount: "",
    categoryId: "",
    scope: "personal" as Scope,
  });
  const [balanceInput, setBalanceInput] = useState("");
  const [transferDate, setTransferDate] = useState(todayISO());
  const [transferAmount, setTransferAmount] = useState("");
  const [recurringDate, setRecurringDate] = useState(todayISO());
  const [recurringAmount, setRecurringAmount] = useState("");
  const [recurringForm, setRecurringForm] = useState<RecurringForm>({
    label: "",
    amount: "",
    categoryId: "",
    scope: "personal",
    frequency: "monthly",
    startDate: todayISO(),
    endDate: "",
    dueDay: String(new Date().getDate()),
    amountIsVariable: false,
  });
  const [allocationForm, setAllocationForm] = useState<Record<string, string>>(
    {},
  );
  const [allocationError, setAllocationError] = useState<string | null>(null);
  const [savingAllocation, setSavingAllocation] = useState(false);
  const [mutationError, setMutationError] = useState<string | null>(null);
  const [mutating, setMutating] = useState(false);

  const dashboard = data.dashboard;
  const categoryById = useMemo(
    () => new Map(data.categories.map((category) => [category.id, category])),
    [data.categories],
  );
  const recurringById = useMemo(
    () => new Map(data.recurring.map((item) => [item.id, item])),
    [data.recurring],
  );
  const myContribution = useMemo(
    () => data.contributions.find((item) => item.user_id === session.user.id),
    [data.contributions, session.user.id],
  );
  const defaultRule = useMemo(
    () => data.allocationRules.find((rule) => rule.is_default),
    [data.allocationRules],
  );
  const allocationTotal = defaultRule
    ? defaultRule.members.reduce(
        (total, member) =>
          total +
          (Number(
            (allocationForm[member.user_id] ?? "0").replace(",", "."),
          ) || 0),
        0,
      )
    : 0;
  const isPersonal = context === "Personnel";
  const balanceCents = dashboard?.personal_balance.balance_cents ?? 0;
  const householdCents =
    dashboard?.deductions.household_contribution_remaining_cents ?? 0;
  const personalRecurringCents =
    dashboard?.deductions.personal_recurring_remaining_cents ?? 0;
  const plannedCents =
    dashboard?.deductions.personal_planned_remaining_cents ?? 0;
  const availableCents = dashboard?.available_forecast_cents ?? 0;
  const groceryAllocatedCents = dashboard?.grocery_budget.allocated_cents ?? 0;
  const grocerySpentCents = dashboard?.grocery_budget.spent_cents ?? 0;
  const groceryRemainingCents =
    dashboard?.grocery_budget.remaining_cents ?? 0;
  const period = dashboard?.period ?? todayISO().slice(0, 7);
  const displayedTransactions = data.transactions.filter((transaction) =>
    isPersonal
      ? transaction.scope === "personal"
      : transaction.scope === "shared",
  );
  const recentPersonal = data.transactions
    .filter((transaction) => transaction.scope === "personal")
    .slice(0, 4);
  const groceryTransactions = data.transactions.filter(
    (transaction) =>
      transaction.scope === "shared" &&
      categoryById.get(transaction.category_id)?.is_grocery === true,
  );
  const contributionTransferred = myContribution?.status === "transferred";
  const lastSyncLabel = data.lastSyncedAt
    ? formatDateTime(data.lastSyncedAt)
    : "jamais";
  const isOffline = !online || data.fromCache;

  useEffect(() => {
    if (form.categoryId === "" && data.categories.length > 0) {
      setForm((current) => ({
        ...current,
        categoryId: data.categories[0].id,
      }));
    }
  }, [data.categories, form.categoryId]);

  useEffect(() => {
    if (defaultRule === undefined) {
      setAllocationForm({});
      return;
    }
    setAllocationForm(
      Object.fromEntries(
        defaultRule.members.map((member) => [
          member.user_id,
          percentageInputValue(member.percentage),
        ]),
      ),
    );
  }, [defaultRule]);

  useEffect(() => {
    if (
      mutationError !== null &&
      !needsBalance &&
      !showAdd &&
      !showBalance &&
      !showContribution &&
      !showRecurring &&
      !showAddRecurring
    ) {
      setMutationError(null);
    }
  }, [
    mutationError,
    needsBalance,
    showAdd,
    showBalance,
    showContribution,
    showRecurring,
    showAddRecurring,
  ]);

  function openExpense() {
    if (!online) return;
    setMutationError(null);
    setShowAdd(true);
  }

  function openBalance() {
    if (!online) return;
    setBalanceInput(centsToInput(balanceCents));
    setMutationError(null);
    setShowBalance(true);
  }

  function openContribution() {
    if (!online || myContribution === undefined) return;
    setTransferAmount(centsToInput(myContribution.amount_cents));
    setTransferDate(todayISO());
    setMutationError(null);
    setShowContribution(true);
  }

  function openRecurring(target: RecurringTarget) {
    if (!online) return;
    setSelectedRecurring(target);
    setRecurringAmount(centsToInput(target.amountCents));
    setRecurringDate(todayISO());
    setMutationError(null);
    setShowRecurring(true);
  }

  function openAddRecurring() {
    if (!online) return;
    setRecurringForm({
      label: "",
      amount: "",
      categoryId: data.categories[0]?.id ?? "",
      scope: "personal",
      frequency: "monthly",
      startDate: todayISO(),
      endDate: "",
      dueDay: String(new Date().getDate()),
      amountIsVariable: false,
    });
    setMutationError(null);
    setShowAddRecurring(true);
  }

  async function saveTransaction(event: FormEvent) {
    event.preventDefault();
    if (!online || mutating) return;
    const amountCents = parseEurosToCents(form.amount);
    if (form.label.trim() === "" || amountCents === null || form.categoryId === "") {
      setMutationError("Renseigne un libellé, un montant positif et une catégorie.");
      return;
    }
    setMutating(true);
    setMutationError(null);
    try {
      await api("/api/v1/transactions", {
        method: "POST",
        body: {
          label: form.label.trim(),
          amount_cents: amountCents,
          transaction_date: todayISO(),
          category_id: form.categoryId,
          scope: form.scope,
          transaction_type: "expense",
        },
      });
      setForm((current) => ({ ...current, label: "", amount: "" }));
      setShowAdd(false);
      await refresh();
    } catch (saveError) {
      setMutationError(errorMessage(saveError));
    } finally {
      setMutating(false);
    }
  }

  async function saveBalance(event: FormEvent) {
    event.preventDefault();
    if (!online || mutating) return;
    const balanceCentsInput = parseSignedEurosToCents(balanceInput);
    if (balanceCentsInput === null) {
      setMutationError("Saisis un solde valide.");
      return;
    }
    setMutating(true);
    setMutationError(null);
    try {
      await api("/api/v1/users/me/personal-balance", {
        method: "PUT",
        body: {
          balance_cents: balanceCentsInput,
          recorded_at: new Date().toISOString(),
        },
      });
      setShowBalance(false);
      await refresh();
    } catch (saveError) {
      setMutationError(errorMessage(saveError));
    } finally {
      setMutating(false);
    }
  }

  async function saveContribution(event: FormEvent) {
    event.preventDefault();
    if (!online || mutating || myContribution === undefined) return;
    const amountCents = parseEurosToCents(transferAmount);
    if (amountCents === null) {
      setMutationError("Saisis un montant transféré valide.");
      return;
    }
    setMutating(true);
    setMutationError(null);
    try {
      await api(
        `/api/v1/households/me/contributions/${myContribution.id}/mark-transferred`,
        {
          method: "POST",
          body: {
            transferred_at: dateInputToInstant(transferDate),
            transferred_amount_cents: amountCents,
          },
        },
      );
      setShowContribution(false);
      await refresh();
    } catch (saveError) {
      setMutationError(errorMessage(saveError));
    } finally {
      setMutating(false);
    }
  }

  async function saveRecurring(event: FormEvent) {
    event.preventDefault();
    if (!online || mutating || selectedRecurring === null) return;
    const amountCents = parseEurosToCents(recurringAmount);
    if (selectedRecurring.amountIsVariable && amountCents === null) {
      setMutationError("Le montant réel est obligatoire pour cette échéance.");
      return;
    }
    setMutating(true);
    setMutationError(null);
    try {
      const body: Record<string, unknown> = {
        paid_at: dateInputToInstant(recurringDate),
      };
      if (amountCents !== null) {
        body.payment_amount_cents = amountCents;
      }
      await api(
        `/api/v1/recurring-occurrences/${selectedRecurring.occurrenceId}/mark-paid`,
        { method: "POST", body },
      );
      setShowRecurring(false);
      setSelectedRecurring(null);
      await refresh();
    } catch (saveError) {
      setMutationError(errorMessage(saveError));
    } finally {
      setMutating(false);
    }
  }

  async function saveRecurringExpense(event: FormEvent) {
    event.preventDefault();
    if (!online || mutating) return;
    const amountCents = recurringForm.amountIsVariable
      ? recurringForm.amount.trim() === ""
        ? null
        : parseEurosToCents(recurringForm.amount)
      : parseEurosToCents(recurringForm.amount);
    if (recurringForm.label.trim() === "" || recurringForm.categoryId === "") {
      setMutationError("Renseigne un libellé et une catégorie.");
      return;
    }
    if (
      amountCents === null &&
      (recurringForm.amount.trim() !== "" || !recurringForm.amountIsVariable)
    ) {
      setMutationError("Renseigne un montant positif valide.");
      return;
    }
    if (
      recurringForm.endDate !== "" &&
      recurringForm.endDate < recurringForm.startDate
    ) {
      setMutationError("La date de fin doit être postérieure à la date de début.");
      return;
    }
    const dueDay =
      recurringForm.frequency === "weekly" || recurringForm.dueDay.trim() === ""
        ? null
        : Number(recurringForm.dueDay);
    if (dueDay !== null && (dueDay < 1 || dueDay > 31)) {
      setMutationError("Le jour d'échéance doit être compris entre 1 et 31.");
      return;
    }

    setMutating(true);
    setMutationError(null);
    try {
      await api("/api/v1/recurring-expenses", {
        method: "POST",
        body: {
          label: recurringForm.label.trim(),
          amount_cents: amountCents,
          category_id: recurringForm.categoryId,
          scope: recurringForm.scope,
          frequency: recurringForm.frequency,
          start_date: recurringForm.startDate,
          end_date: recurringForm.endDate === "" ? null : recurringForm.endDate,
          due_day: dueDay,
          amount_is_variable: recurringForm.amountIsVariable,
        },
      });
      setShowAddRecurring(false);
      await refresh();
    } catch (saveError) {
      setMutationError(errorMessage(saveError));
    } finally {
      setMutating(false);
    }
  }

  async function saveAllocation() {
    if (!online || savingAllocation || defaultRule === undefined) return;
    const members = defaultRule.members.map((member) => ({
      user_id: member.user_id,
      percentage: (allocationForm[member.user_id] ?? "0").replace(",", "."),
    }));
    const percentages = members.map((member) => Number(member.percentage));
    if (
      percentages.some(
        (percentage) =>
          !Number.isFinite(percentage) ||
          percentage < 0 ||
          percentage > 100,
      )
    ) {
      setAllocationError("Chaque pourcentage doit être compris entre 0 et 100.");
      return;
    }
    const total = percentages.reduce((sum, percentage) => sum + percentage, 0);
    if (total > 100.0001) {
      setAllocationError("La somme des pourcentages ne peut pas dépasser 100 %.");
      return;
    }
    if (defaultRule.members.length > 1 && Math.abs(total - 100) > 0.0001) {
      setAllocationError("La somme des pourcentages doit être égale à 100 %.");
      return;
    }

    setSavingAllocation(true);
    setAllocationError(null);
    try {
      await api("/api/v1/households/me/allocation-rules/default", {
        method: "PUT",
        body: { members },
      });
      await refresh();
    } catch (saveError) {
      setAllocationError(errorMessage(saveError));
    } finally {
      setSavingAllocation(false);
    }
  }

  if (needsBalance) {
    return (
      <BalanceOnboarding
        online={online}
        initialValue={balanceInput}
        error={mutationError}
        submitting={mutating}
        onLogout={onLogout}
        onSubmit={async (value) => {
          const cents = parseSignedEurosToCents(value);
          if (cents === null) {
            setMutationError("Saisis un solde valide.");
            return;
          }
          setMutating(true);
          setMutationError(null);
          try {
            await api("/api/v1/users/me/personal-balance", {
              method: "PUT",
              body: {
                balance_cents: cents,
                recorded_at: new Date().toISOString(),
              },
            });
            await refresh();
          } catch (saveError) {
            setMutationError(errorMessage(saveError));
          } finally {
            setMutating(false);
          }
        }}
      />
    );
  }

  if (loading && dashboard === null) {
    return <SplashScreen label="Chargement de ton espace…" />;
  }

  if (dashboard === null) {
    return (
      <ErrorScreen
        message={error ?? "Impossible de charger le tableau de bord."}
        online={online}
        onRetry={refresh}
        onLogout={onLogout}
      />
    );
  }

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
        <div className="brand">
          <div className="brand-mark">
            <Wallet size={21} />
          </div>
          <span>
            mes<strong>dépenses</strong>
          </span>
          <button
            className="icon-btn close-menu"
            onClick={() => setMobileMenu(false)}
            aria-label="Fermer"
          >
            <X size={19} />
          </button>
        </div>
        <div className="workspace-label">ESPACE</div>
        <div className="context-switch">
          <div className="avatar">{isPersonal ? "A" : "F"}</div>
          <div className="context-copy">
            <strong>{isPersonal ? "Mon espace" : "Notre foyer"}</strong>
            <span>{isPersonal ? "Vue personnelle" : "Vue partagée"}</span>
          </div>
          <ChevronDown size={16} className="muted" />
          <select
            aria-label="Changer de contexte"
            value={context}
            onChange={(event) => setContext(event.target.value as Context)}
          >
            <option>Personnel</option>
            <option>Foyer</option>
          </select>
        </div>
        <nav className="main-nav">
          <div className="nav-caption">GESTION</div>
          {nav.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.label}
                className={`nav-item ${section === item.label ? "active" : ""}`}
                onClick={() => {
                  setSection(item.label);
                  setMobileMenu(false);
                }}
              >
                <Icon size={18} />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item">
            <Settings size={18} />
            <span>Paramètres</span>
          </button>
          <div className="profile session-profile">
            <div className="avatar avatar-small">
              {session.user.first_name.slice(0, 1).toUpperCase()}
            </div>
            <div>
              <strong>{session.user.first_name}</strong>
              <span>{session.user.email}</span>
            </div>
            <button
              className="icon-btn logout-button"
              onClick={() => void onLogout()}
              aria-label="Se déconnecter"
              title="Se déconnecter"
            >
              <LogOut size={17} />
            </button>
          </div>
        </div>
      </aside>
      {mobileMenu && (
        <button
          className="mobile-scrim"
          onClick={() => setMobileMenu(false)}
          aria-label="Fermer le menu"
        />
      )}
      <main className="main-area">
        <header className="topbar">
          <button
            className="icon-btn mobile-menu-btn"
            onClick={() => setMobileMenu(true)}
            aria-label="Ouvrir le menu"
          >
            <Menu size={21} />
          </button>
          <div className="breadcrumb">
            <span>{isPersonal ? "Mon espace" : "Notre foyer"}</span>
            <span className="crumb-sep">/</span>
            <strong>{section}</strong>
          </div>
          <div className="top-actions">
            <div className="period">
              <CalendarDays size={16} />
              <span>{periodLabel(period)}</span>
              <ChevronDown size={14} />
            </div>
            <button
              className="icon-btn notification-btn"
              aria-label={`Notifications${
                data.unreadCount > 0 ? ` (${data.unreadCount} non lues)` : ""
              }`}
            >
              <Bell size={19} />
              {data.unreadCount > 0 && (
                <span className="notification-count">{data.unreadCount}</span>
              )}
            </button>
            <button
              className="add-button"
              onClick={openExpense}
              disabled={!online}
              title={online ? undefined : "Indisponible hors ligne"}
            >
              <Plus size={18} />
              <span>Ajouter une dépense</span>
            </button>
          </div>
        </header>

        {isOffline && (
          <div className="offline-banner" role="status">
            <WifiOff size={16} />
            <span>
              Hors ligne · consultation en lecture seule · dernière
              synchronisation : {lastSyncLabel}
            </span>
          </div>
        )}
        {error !== null && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            <button className="text-link" onClick={() => void refresh()}>
              <RefreshCw size={14} /> Réessayer
            </button>
          </div>
        )}

        {section === "Vue d'ensemble" ? (
          <div className="page-content">
            <div className="page-heading">
              <div>
                <div className="eyebrow">{periodLabel(period).toUpperCase()}</div>
                <h1>{isPersonal ? "Mon budget personnel" : "Budget du foyer"}</h1>
                <p>
                  {isPersonal
                    ? "Ton disponible prévisionnel jusqu'à la fin du mois."
                    : "Les charges communes et le budget courses."}
                </p>
              </div>
              {isPersonal && (
                <button
                  className="outline-button"
                  onClick={openBalance}
                  disabled={!online}
                >
                  <Pencil size={15} /> Modifier le solde
                </button>
              )}
            </div>

            {isPersonal ? (
              <>
                <section className="summary-grid">
                  <article className="summary-card primary-card">
                    <div className="card-top">
                      <span>Disponible prévisionnel</span>
                      <span className="card-icon">
                        <Wallet size={18} />
                      </span>
                    </div>
                    <div className="big-number">{euro(availableCents)}</div>
                    <div className="card-foot">
                      Après déduction des sorties non encore reflétées dans le
                      solde saisi
                    </div>
                    <div className="primary-decoration" />
                  </article>
                  <article className="summary-card">
                    <div className="card-top">
                      <span>Solde du compte personnel</span>
                      <span className="soft-icon violet">
                        <Wallet size={18} />
                      </span>
                    </div>
                    <div className="big-number dark-number">
                      {euro(balanceCents)}
                    </div>
                    <div className="card-foot">
                      <span>Saisie manuelle</span>
                      <strong>
                        {formatDateTime(
                          dashboard.personal_balance.recorded_at,
                        )}
                      </strong>
                    </div>
                  </article>
                  <article className="summary-card">
                    <div className="card-top">
                      <span>Charges restantes</span>
                      <span className="soft-icon blue">
                        <ArrowDownRight size={18} />
                      </span>
                    </div>
                    <div className="big-number dark-number">
                      {euro(
                        householdCents +
                          personalRecurringCents +
                          plannedCents,
                      )}
                    </div>
                    <div className="card-foot">À déduire ce mois-ci</div>
                  </article>
                </section>

                <section className="content-grid">
                  <article className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Ce qui reste à payer</h2>
                        <p>Une seule ligne pour ta participation au foyer</p>
                      </div>
                      <button
                        className="text-link"
                        onClick={() => setSection("Charges récurrentes")}
                      >
                        Voir les charges <ArrowUpRight size={15} />
                      </button>
                    </div>
                    <div className="deduction-list">
                      <div className="deduction-row">
                        <div className="budget-symbol violet">
                          <House size={17} />
                        </div>
                        <div className="deduction-copy">
                          <strong>Participation au foyer</strong>
                          <span>
                            Charges communes + contribution courses
                            {defaultRule
                              ? ` · ${percentageFor(defaultRule, session.user.id)} %`
                              : ""}
                          </span>
                        </div>
                        <strong>{euro(householdCents)}</strong>
                      </div>
                      <div className="deduction-row">
                        <div className="budget-symbol blue">
                          <Repeat2 size={17} />
                        </div>
                        <div className="deduction-copy">
                          <strong>Charges personnelles</strong>
                          <span>Abonnements et prélèvements à venir</span>
                        </div>
                        <strong>{euro(personalRecurringCents)}</strong>
                      </div>
                      <div className="deduction-row">
                        <div className="budget-symbol orange">
                          <CalendarDays size={17} />
                        </div>
                        <div className="deduction-copy">
                          <strong>Dépenses ponctuelles prévues</strong>
                          <span>Non encore payées</span>
                        </div>
                        <strong>{euro(plannedCents)}</strong>
                      </div>
                    </div>
                    <div className="contribution-action">
                      <span>
                        {contributionTransferred
                          ? "Virement effectué"
                          : "Virement à effectuer"}
                      </span>
                      <p className="form-hint">
                        Le pointage demande la date et le montant réellement
                        transféré. Le montant reste déduit jusqu'à une nouvelle
                        saisie du solde bancaire après le virement.
                      </p>
                      {!contributionTransferred && myContribution !== undefined && (
                        <button
                          className="outline-button"
                          onClick={openContribution}
                          disabled={!online}
                        >
                          <Check size={15} /> Pointer le virement
                        </button>
                      )}
                    </div>
                  </article>
                  <article className="panel grocery-panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Budget courses du foyer</h2>
                        <p>Enveloppe commune · {periodLabel(period)}</p>
                      </div>
                      <span className="soft-icon violet">
                        <ShoppingBasket size={18} />
                      </span>
                    </div>
                    <div className="grocery-total">
                      <strong>{euro(groceryRemainingCents)}</strong>
                      <span>restants sur {euro(groceryAllocatedCents)}</span>
                    </div>
                    <div className="progress-track">
                      <span
                        className="progress-fill violet-fill"
                        style={{
                          width: `${progress(grocerySpentCents, groceryAllocatedCents)}%`,
                        }}
                      />
                    </div>
                    <div className="card-foot">
                      <span>{euro(grocerySpentCents)} dépensés</span>
                      <strong>
                        {progress(grocerySpentCents, groceryAllocatedCents)} %
                        utilisé
                      </strong>
                    </div>
                    <p className="grocery-note">
                      <CircleHelp size={14} /> Les courses communes ne sont pas
                      déduites de ton disponible personnel.
                    </p>
                  </article>
                </section>

                <section className="content-grid lower-grid">
                  <article className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Charges récurrentes</h2>
                        <p>Prochaines échéances</p>
                      </div>
                      <button
                        className="text-link"
                        onClick={() => setSection("Charges récurrentes")}
                      >
                        Tout voir <ArrowUpRight size={15} />
                      </button>
                    </div>
                    <div className="transaction-list">
                      {dashboard.upcoming_recurring.length === 0 && (
                        <EmptyState label="Aucune échéance à venir." />
                      )}
                      {dashboard.upcoming_recurring.slice(0, 5).map((item) => {
                        const recurring = recurringById.get(
                          item.recurring_expense_id,
                        );
                        return (
                          <div className="transaction-row" key={item.occurrence_id}>
                            <div
                              className={`transaction-symbol ${
                                recurring?.scope === "shared" ? "purple" : "blue"
                              }`}
                            >
                              {recurring?.scope === "shared" ? (
                                <House size={17} />
                              ) : (
                                <Repeat2 size={17} />
                              )}
                            </div>
                            <div className="transaction-main">
                              <strong>{item.label}</strong>
                              <span>
                                {recurring?.scope === "shared"
                                  ? "Charge commune"
                                  : "Charge personnelle"}{" "}
                                · {formatDate(item.due_date)} ·{" "}
                                {statusLabel(item.status)}
                              </span>
                            </div>
                            <strong className="transaction-amount">
                              {euro(item.amount_cents)}
                            </strong>
                            {item.status !== "paid" && (
                              <button
                                className="recurring-check"
                                onClick={() =>
                                  openRecurring({
                                    occurrenceId: item.occurrence_id,
                                    label: item.label,
                                    amountCents: item.amount_cents,
                                    amountIsVariable:
                                      recurring?.amount_is_variable ?? false,
                                    dueDate: item.due_date,
                                  })
                                }
                                disabled={!online}
                              >
                                Pointer
                              </button>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </article>
                  <article className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Dernières dépenses personnelles</h2>
                        <p>Les dépenses communes sont exclues</p>
                      </div>
                      <button
                        className="text-link"
                        onClick={() => setSection("Dépenses")}
                      >
                        Tout voir <ArrowUpRight size={15} />
                      </button>
                    </div>
                    <div className="transaction-list">
                      {recentPersonal.length === 0 && (
                        <EmptyState label="Aucune dépense personnelle." />
                      )}
                      {recentPersonal.map((transaction) => (
                        <TransactionRow
                          key={transaction.id}
                          transaction={transaction}
                          category={categoryById.get(transaction.category_id)}
                        />
                      ))}
                    </div>
                  </article>
                </section>
              </>
            ) : (
              <>
                <section className="summary-grid">
                  <article className="summary-card primary-card">
                    <div className="card-top">
                      <span>Budget courses</span>
                      <span className="card-icon">
                        <ShoppingBasket size={18} />
                      </span>
                    </div>
                    <div className="big-number">
                      {euro(groceryRemainingCents)}
                    </div>
                    <div className="card-foot">
                      Restants sur {euro(groceryAllocatedCents)}
                    </div>
                    <div className="primary-decoration" />
                  </article>
                  <article className="summary-card">
                    <div className="card-top">
                      <span>Charges communes restantes</span>
                      <span className="soft-icon violet">
                        <House size={18} />
                      </span>
                    </div>
                    <div className="big-number dark-number">
                      {euro(householdCents)}
                    </div>
                    <div className="card-foot">
                      Participation agrégée du foyer
                    </div>
                  </article>
                  <article className="summary-card">
                    <div className="card-top">
                      <span>Répartition actuelle</span>
                      <span className="soft-icon blue">
                        <Scale size={18} />
                      </span>
                    </div>
                    <div className="big-number dark-number">
                      {defaultRule
                        ? defaultRule.members
                            .map((member) =>
                              Number(member.percentage).toFixed(0),
                            )
                            .join(" / ")
                        : "—"}
                    </div>
                    <div className="card-foot">Règle par défaut du foyer</div>
                  </article>
                </section>

                <section className="content-grid">
                  <article className="panel grocery-panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Enveloppe courses</h2>
                        <p>Budget mensuel partagé</p>
                      </div>
                    </div>
                    <div className="grocery-total">
                      <strong>{euro(groceryRemainingCents)}</strong>
                      <span>restants sur {euro(groceryAllocatedCents)}</span>
                    </div>
                    <div className="progress-track">
                      <span
                        className="progress-fill violet-fill"
                        style={{
                          width: `${progress(grocerySpentCents, groceryAllocatedCents)}%`,
                        }}
                      />
                    </div>
                    <div className="card-foot">
                      <span>{euro(grocerySpentCents)} dépensés</span>
                      <strong>
                        {progress(grocerySpentCents, groceryAllocatedCents)} %
                        utilisé
                      </strong>
                    </div>
                  </article>
                  <article className="panel">
                    <div className="panel-heading">
                      <div>
                        <h2>Contribution au budget courses</h2>
                        <p>Répartition par défaut</p>
                      </div>
                    </div>
                    {defaultRule?.members.map((member) => (
                      <div className="deduction-row" key={member.user_id}>
                        <div className="deduction-copy">
                          <strong>
                            {member.first_name} ·{" "}
                            {Number(member.percentage).toFixed(0)} %
                          </strong>
                        </div>
                        <strong>
                          {euro(
                            Math.round(
                              (groceryAllocatedCents *
                                Number(member.percentage)) /
                                100,
                            ),
                          )}
                        </strong>
                      </div>
                    ))}
                    {defaultRule === undefined && (
                      <EmptyState label="Aucune règle de répartition." />
                    )}
                  </article>
                </section>
                <article className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Dépenses communes de courses</h2>
                      <p>
                        Chaque achat diminue uniquement l'enveloppe commune
                      </p>
                    </div>
                  </div>
                  <div className="transaction-list">
                    {groceryTransactions.length === 0 && (
                      <EmptyState label="Aucun achat de courses enregistré." />
                    )}
                    {groceryTransactions.map((transaction) => (
                      <TransactionRow
                        key={transaction.id}
                        transaction={transaction}
                        category={categoryById.get(transaction.category_id)}
                      />
                    ))}
                  </div>
                </article>
              </>
            )}
            <div className="dashboard-footer">
              <span>
                {isOffline
                  ? `Données consultées hors ligne · ${lastSyncLabel}`
                  : `Dernière synchronisation · ${lastSyncLabel}`}
              </span>
              <span>Solde saisi manuellement · Aucune connexion bancaire</span>
            </div>
          </div>
        ) : (
          <div className="page-content">
            <div className="page-heading">
              <div>
                <div className="eyebrow">
                  {isPersonal ? "ESPACE PERSONNEL" : "ESPACE FOYER"}
                </div>
                <h1>{section}</h1>
                <p>{sectionDescription(section)}</p>
              </div>
              {section === "Dépenses" && (
                <button
                  className="add-button"
                  onClick={openExpense}
                  disabled={!online}
                >
                  <Plus size={16} /> Ajouter
                </button>
              )}
              {section === "Charges récurrentes" && (
                <button
                  className="add-button"
                  onClick={openAddRecurring}
                  disabled={!online}
                >
                  <Plus size={16} /> Ajouter une charge
                </button>
              )}
            </div>

            {section === "Dépenses" && (
              <article className="panel">
                <div className="transaction-list">
                  {displayedTransactions.length === 0 && (
                    <EmptyState label="Aucune dépense sur ce périmètre." />
                  )}
                  {displayedTransactions.map((transaction) => (
                    <TransactionRow
                      key={transaction.id}
                      transaction={transaction}
                      category={categoryById.get(transaction.category_id)}
                    />
                  ))}
                </div>
              </article>
            )}

            {section === "Charges récurrentes" && (
              <article className="panel">
                <div className="transaction-list">
                  {dashboard.upcoming_recurring.length === 0 && (
                    <div className="empty-state">
                      <p>Aucune échéance à venir.</p>
                      <button
                        className="outline-button"
                        onClick={openAddRecurring}
                        disabled={!online}
                      >
                        <Plus size={16} /> Ajouter une charge récurrente
                      </button>
                    </div>
                  )}
                  {dashboard.upcoming_recurring.map((item) => {
                    const recurring = recurringById.get(
                      item.recurring_expense_id,
                    );
                    return (
                      <div className="transaction-row" key={item.occurrence_id}>
                        <div
                          className={`transaction-symbol ${
                            recurring?.scope === "shared" ? "purple" : "blue"
                          }`}
                        >
                          {recurring?.scope === "shared" ? (
                            <House size={17} />
                          ) : (
                            <Repeat2 size={17} />
                          )}
                        </div>
                        <div className="transaction-main">
                          <strong>{item.label}</strong>
                          <span>
                            Échéance {formatDate(item.due_date)} ·{" "}
                            {statusLabel(item.status)}
                            {recurring?.amount_is_variable
                              ? " · montant variable"
                              : ""}
                          </span>
                        </div>
                        <strong className="transaction-amount">
                          {euro(item.amount_cents)}
                        </strong>
                        {item.status !== "paid" && (
                          <button
                            className="recurring-check"
                            onClick={() =>
                              openRecurring({
                                occurrenceId: item.occurrence_id,
                                label: item.label,
                                amountCents: item.amount_cents,
                                amountIsVariable:
                                  recurring?.amount_is_variable ?? false,
                                dueDate: item.due_date,
                              })
                            }
                            disabled={!online}
                          >
                            Pointer
                          </button>
                        )}
                      </div>
                    );
                  })}
                </div>
              </article>
            )}

            {section === "Budget courses" && (
              <section className="content-grid">
                <article className="panel grocery-panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Enveloppe courses</h2>
                      <p>{periodLabel(period)}</p>
                    </div>
                  </div>
                  <div className="grocery-total">
                    <strong>{euro(groceryRemainingCents)}</strong>
                    <span>restants sur {euro(groceryAllocatedCents)}</span>
                  </div>
                  <div className="progress-track">
                    <span
                      className="progress-fill violet-fill"
                      style={{
                        width: `${progress(grocerySpentCents, groceryAllocatedCents)}%`,
                      }}
                    />
                  </div>
                </article>
                <article className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Achats de courses</h2>
                      <p>Dépenses communes imputées au budget</p>
                    </div>
                  </div>
                  <div className="transaction-list">
                    {groceryTransactions.length === 0 && (
                      <EmptyState label="Aucun achat de courses." />
                    )}
                    {groceryTransactions.map((transaction) => (
                      <TransactionRow
                        key={transaction.id}
                        transaction={transaction}
                        category={categoryById.get(transaction.category_id)}
                      />
                    ))}
                  </div>
                </article>
              </section>
            )}

            {section === "Répartition" && (
              <section className="content-grid">
                <article className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Règle par défaut</h2>
                      <p>Répartition des charges communes</p>
                    </div>
                  </div>
                  {defaultRule?.members.map((member) => (
                    <div className="deduction-row" key={member.user_id}>
                      <div className="deduction-copy">
                        <strong>{member.first_name}</strong>
                        <span>{member.email}</span>
                      </div>
                      {session.role === "owner" ? (
                        <label className="percentage-field">
                          <input
                            className="percentage-input"
                            type="number"
                            min="0"
                            max="100"
                            step="0.1"
                            value={allocationForm[member.user_id] ?? ""}
                            onChange={(event) =>
                              setAllocationForm({
                                ...allocationForm,
                                [member.user_id]: event.target.value,
                              })
                            }
                            aria-label={`Pourcentage de ${member.first_name}`}
                          />
                          <span>%</span>
                        </label>
                      ) : (
                        <strong>
                          {Number(member.percentage).toFixed(0)} %
                        </strong>
                      )}
                    </div>
                  ))}
                  {defaultRule !== undefined && (
                    <>
                      <div className="card-foot">
                        <span>Total attribué</span>
                        <strong>
                          {allocationTotal.toLocaleString("fr-FR", {
                            maximumFractionDigits: 2,
                          })}{" "}
                          %
                        </strong>
                      </div>
                      {defaultRule.members.length === 1 && (
                        <div className="allocation-actions">
                          <button
                            type="button"
                            className="outline-button"
                            onClick={() =>
                              setAllocationForm({
                                [defaultRule.members[0].user_id]: "55",
                              })
                            }
                            disabled={!online || session.role !== "owner"}
                          >
                            Appliquer 55 %
                          </button>
                          <button
                            type="button"
                            className="outline-button"
                            onClick={() =>
                              setAllocationForm({
                                [defaultRule.members[0].user_id]: "100",
                              })
                            }
                            disabled={!online || session.role !== "owner"}
                          >
                            Remettre 100 %
                          </button>
                        </div>
                      )}
                      <p className="form-hint">
                        {defaultRule.members.length === 1
                          ? "Une part inférieure à 100 % laisse le reste non attribué : il ne sera pas suivi dans les contributions."
                          : "La somme des pourcentages doit être égale à 100 %."}
                      </p>
                      {allocationError !== null && (
                        <p className="form-error" role="alert">
                          {allocationError}
                        </p>
                      )}
                      {session.role === "owner" ? (
                        <button
                          type="button"
                          className="add-button"
                          onClick={() => void saveAllocation()}
                          disabled={!online || savingAllocation}
                        >
                          <Check size={16} /> Enregistrer la répartition
                        </button>
                      ) : (
                        <p className="form-hint">
                          Seul le propriétaire du foyer peut modifier la
                          répartition.
                        </p>
                      )}
                    </>
                  )}
                  {defaultRule === undefined && (
                    <EmptyState label="Aucune règle de répartition." />
                  )}
                </article>
                <article className="panel">
                  <div className="panel-heading">
                    <div>
                      <h2>Contributions du mois</h2>
                      <p>{periodLabel(period)}</p>
                    </div>
                  </div>
                  {data.contributions.length === 0 && (
                    <EmptyState label="Aucune contribution calculée." />
                  )}
                  {data.contributions.map((contribution) => (
                    <div className="deduction-row" key={contribution.id}>
                      <div className="deduction-copy">
                        <strong>{contribution.first_name}</strong>
                        <span>{contributionStatus(contribution.status)}</span>
                      </div>
                      <strong>{euro(contribution.amount_cents)}</strong>
                    </div>
                  ))}
                </article>
              </section>
            )}

            {section === "Historique" && (
              <article className="panel">
                <div className="transaction-list">
                  {data.transactions.length === 0 && (
                    <EmptyState label="Aucune transaction enregistrée." />
                  )}
                  {data.transactions.map((transaction) => (
                    <TransactionRow
                      key={transaction.id}
                      transaction={transaction}
                      category={categoryById.get(transaction.category_id)}
                      showScope
                    />
                  ))}
                </div>
              </article>
            )}
          </div>
        )}
      </main>

      <nav className="mobile-bottom-nav">
        {nav.slice(0, 4).map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.label}
              className={section === item.label ? "selected" : ""}
              onClick={() => setSection(item.label)}
            >
              <Icon size={19} />
              <span>
                {item.label === "Vue d'ensemble"
                  ? "Accueil"
                  : item.label === "Dépenses"
                    ? "Dépenses"
                    : item.label === "Charges récurrentes"
                      ? "Charges"
                      : "Courses"}
              </span>
            </button>
          );
        })}
      </nav>

      {showContribution && myContribution !== undefined && (
        <Modal
          title="Pointer la participation au foyer"
          subtitle="Confirme les informations du virement réellement effectué."
          onClose={() => setShowContribution(false)}
        >
          <form onSubmit={saveContribution}>
            <label>
              Date réelle du virement
              <input
                type="date"
                value={transferDate}
                onChange={(event) => setTransferDate(event.target.value)}
              />
            </label>
            <label>
              Montant réellement transféré (€)
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={transferAmount}
                onChange={(event) => setTransferAmount(event.target.value)}
              />
            </label>
            {mutationError !== null && (
              <p className="form-error" role="alert">
                {mutationError}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="outline-button"
                onClick={() => setShowContribution(false)}
              >
                Annuler
              </button>
              <button
                type="submit"
                className="add-button"
                disabled={!online || mutating}
              >
                <Check size={16} /> Confirmer le virement
              </button>
            </div>
          </form>
        </Modal>
      )}

      {showBalance && (
        <Modal
          title="Mettre à jour le solde"
          subtitle="Saisis le solde réel de ton compte courant personnel."
          onClose={() => setShowBalance(false)}
        >
          <form onSubmit={saveBalance}>
            <label>
              Solde actuel (€)
              <input
                type="number"
                step="0.01"
                value={balanceInput}
                onChange={(event) => setBalanceInput(event.target.value)}
              />
            </label>
            <p className="form-hint">
              Cette saisie horodatée devient le nouvel instantané de référence.
            </p>
            {mutationError !== null && (
              <p className="form-error" role="alert">
                {mutationError}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="outline-button"
                onClick={() => setShowBalance(false)}
              >
                Annuler
              </button>
              <button
                type="submit"
                className="add-button"
                disabled={!online || mutating}
              >
                <Check size={16} /> Enregistrer
              </button>
            </div>
          </form>
        </Modal>
      )}

      {showAdd && (
        <Modal
          title="Nouvelle dépense"
          subtitle="Choisis si la dépense est personnelle ou commune."
          onClose={() => setShowAdd(false)}
        >
          <form onSubmit={saveTransaction}>
            <label>
              Libellé
              <input
                placeholder="Ex. Courses de la semaine"
                value={form.label}
                onChange={(event) =>
                  setForm({ ...form, label: event.target.value })
                }
              />
            </label>
            <div className="form-two">
              <label>
                Montant (€)
                <input
                  type="number"
                  step="0.01"
                  placeholder="0,00"
                  value={form.amount}
                  onChange={(event) =>
                    setForm({ ...form, amount: event.target.value })
                  }
                />
              </label>
              <label>
                Catégorie
                <select
                  value={form.categoryId}
                  onChange={(event) =>
                    setForm({ ...form, categoryId: event.target.value })
                  }
                >
                  {data.categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label>
              Type de dépense
              <select
                value={form.scope}
                onChange={(event) =>
                  setForm({ ...form, scope: event.target.value as Scope })
                }
              >
                <option value="personal">Personnelle</option>
                <option value="shared">Commune</option>
              </select>
            </label>
            {form.scope === "shared" &&
              categoryById.get(form.categoryId)?.is_grocery === true && (
                <p className="form-hint">
                  Déduite du budget courses commun, pas du disponible personnel.
                </p>
              )}
            {form.scope === "shared" &&
              categoryById.get(form.categoryId)?.is_grocery === false && (
                <p className="form-hint">
                  Répartie selon la règle du foyer et intégrée à la participation
                  au foyer.
                </p>
              )}
            {mutationError !== null && (
              <p className="form-error" role="alert">
                {mutationError}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="outline-button"
                onClick={() => setShowAdd(false)}
              >
                Annuler
              </button>
              <button
                type="submit"
                className="add-button"
                disabled={!online || mutating}
              >
                Enregistrer
              </button>
            </div>
          </form>
        </Modal>
      )}

      {showAddRecurring && (
        <Modal
          title="Nouvelle charge récurrente"
          subtitle="Ajoute un abonnement, un prélèvement ou une charge commune."
          onClose={() => setShowAddRecurring(false)}
        >
          <form onSubmit={saveRecurringExpense}>
            <label>
              Libellé
              <input
                placeholder="Ex. Assurance auto"
                value={recurringForm.label}
                onChange={(event) =>
                  setRecurringForm({
                    ...recurringForm,
                    label: event.target.value,
                  })
                }
              />
            </label>
            <div className="form-two">
              <label>
                Montant (€)
                <input
                  type="number"
                  min="0.01"
                  step="0.01"
                  placeholder={
                    recurringForm.amountIsVariable ? "Facultatif" : "0,00"
                  }
                  value={recurringForm.amount}
                  onChange={(event) =>
                    setRecurringForm({
                      ...recurringForm,
                      amount: event.target.value,
                    })
                  }
                />
              </label>
              <label>
                Catégorie
                <select
                  value={recurringForm.categoryId}
                  onChange={(event) =>
                    setRecurringForm({
                      ...recurringForm,
                      categoryId: event.target.value,
                    })
                  }
                >
                  {data.categories.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            <label className="checkbox-row">
              <input
                type="checkbox"
                checked={recurringForm.amountIsVariable}
                onChange={(event) =>
                  setRecurringForm({
                    ...recurringForm,
                    amountIsVariable: event.target.checked,
                  })
                }
              />
              Montant variable
            </label>
            <div className="form-two">
              <label>
                Type
                <select
                  value={recurringForm.scope}
                  onChange={(event) =>
                    setRecurringForm({
                      ...recurringForm,
                      scope: event.target.value as Scope,
                    })
                  }
                >
                  <option value="personal">Personnelle</option>
                  <option value="shared">Commune</option>
                </select>
              </label>
              <label>
                Fréquence
                <select
                  value={recurringForm.frequency}
                  onChange={(event) =>
                    setRecurringForm({
                      ...recurringForm,
                      frequency: event.target
                        .value as RecurringForm["frequency"],
                    })
                  }
                >
                  <option value="weekly">Hebdomadaire</option>
                  <option value="monthly">Mensuelle</option>
                  <option value="quarterly">Trimestrielle</option>
                  <option value="semiannual">Semestrielle</option>
                  <option value="yearly">Annuelle</option>
                </select>
              </label>
            </div>
            <div className="form-two">
              <label>
                Date de début
                <input
                  type="date"
                  value={recurringForm.startDate}
                  onChange={(event) =>
                    setRecurringForm({
                      ...recurringForm,
                      startDate: event.target.value,
                    })
                  }
                />
              </label>
              <label>
                Date de fin (facultatif)
                <input
                  type="date"
                  value={recurringForm.endDate}
                  onChange={(event) =>
                    setRecurringForm({
                      ...recurringForm,
                      endDate: event.target.value,
                    })
                  }
                />
              </label>
            </div>
            {recurringForm.frequency !== "weekly" && (
              <label>
                Jour d'échéance
                <input
                  type="number"
                  min="1"
                  max="31"
                  value={recurringForm.dueDay}
                  onChange={(event) =>
                    setRecurringForm({
                      ...recurringForm,
                      dueDay: event.target.value,
                    })
                  }
                />
              </label>
            )}
            {recurringForm.scope === "shared" &&
              categoryById.get(recurringForm.categoryId)?.is_grocery === true && (
                <p className="form-hint">
                  Cette charge commune de courses sera imputée au budget courses.
                </p>
              )}
            {mutationError !== null && (
              <p className="form-error" role="alert">
                {mutationError}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="outline-button"
                onClick={() => setShowAddRecurring(false)}
              >
                Annuler
              </button>
              <button
                type="submit"
                className="add-button"
                disabled={!online || mutating}
              >
                <Check size={16} /> Créer la charge
              </button>
            </div>
          </form>
        </Modal>
      )}

      {showRecurring && selectedRecurring !== null && (
        <Modal
          title={`Pointer · ${selectedRecurring.label}`}
          subtitle="Confirme la date et le montant réellement payés."
          onClose={() => setShowRecurring(false)}
        >
          <form onSubmit={saveRecurring}>
            <label>
              Date réelle du paiement
              <input
                type="date"
                value={recurringDate}
                onChange={(event) => setRecurringDate(event.target.value)}
              />
            </label>
            <label>
              Montant réellement payé (€)
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={recurringAmount}
                onChange={(event) => setRecurringAmount(event.target.value)}
              />
            </label>
            {selectedRecurring.amountIsVariable && (
              <p className="form-hint">
                Montant variable : confirme le montant réellement débité.
              </p>
            )}
            {mutationError !== null && (
              <p className="form-error" role="alert">
                {mutationError}
              </p>
            )}
            <div className="modal-actions">
              <button
                type="button"
                className="outline-button"
                onClick={() => setShowRecurring(false)}
              >
                Annuler
              </button>
              <button
                type="submit"
                className="add-button"
                disabled={!online || mutating}
              >
                <Check size={16} /> Pointer comme payée
              </button>
            </div>
          </form>
        </Modal>
      )}
    </div>
  );
}

function TransactionRow({
  transaction,
  category,
  showScope = false,
}: {
  transaction: Transaction;
  category: Category | undefined;
  showScope?: boolean;
}) {
  const visual = categoryVisual(category?.name ?? "Divers");
  const Icon = visual.Icon;
  const isRefund = transaction.transaction_type === "refund";
  return (
    <div className="transaction-row">
      <div className={`transaction-symbol ${visual.tone}`}>
        <Icon size={17} />
      </div>
      <div className="transaction-main">
        <strong>{transaction.label}</strong>
        <span>
          {category?.name ?? "Sans catégorie"} ·{" "}
          {formatDate(transaction.transaction_date)}
          {showScope
            ? ` · ${transaction.scope === "personal" ? "Personnel" : "Foyer"}`
            : ""}
        </span>
      </div>
      <strong className="transaction-amount">
        {isRefund ? "+" : "−"} {euro(transaction.amount_cents)}
      </strong>
    </div>
  );
}

function Modal({
  title,
  subtitle,
  onClose,
  children,
}: {
  title: string;
  subtitle: string;
  onClose: () => void;
  children: ReactNode;
}) {
  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(event) => event.stopPropagation()}>
        <div className="modal-heading">
          <div>
            <h2>{title}</h2>
            <p>{subtitle}</p>
          </div>
          <button className="icon-btn" onClick={onClose} aria-label="Fermer">
            <X size={19} />
          </button>
        </div>
        {children}
      </div>
    </div>
  );
}

function BalanceOnboarding({
  online,
  initialValue,
  error,
  submitting,
  onSubmit,
  onLogout,
}: {
  online: boolean;
  initialValue: string;
  error: string | null;
  submitting: boolean;
  onSubmit: (value: string) => Promise<void>;
  onLogout: () => Promise<void>;
}) {
  const [value, setValue] = useState(initialValue);
  return (
    <main className="login-screen">
      <section className="login-card">
        <div className="brand login-brand">
          <div className="brand-mark">
            <Wallet size={21} />
          </div>
          <span>
            mes<strong>dépenses</strong>
          </span>
        </div>
        <h1>Dernière étape</h1>
        <p className="login-subtitle">
          Saisis le solde de ton compte courant personnel pour calculer ton
          disponible prévisionnel.
        </p>
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void onSubmit(value);
          }}
        >
          <label>
            Solde actuel (€)
            <input
              type="number"
              step="0.01"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              required
            />
          </label>
          {error !== null && (
            <p className="form-error" role="alert">
              {error}
            </p>
          )}
          <button
            className="add-button login-submit"
            type="submit"
            disabled={!online || submitting}
          >
            <Check size={17} /> Enregistrer mon solde
          </button>
        </form>
        <button
          className="text-link"
          onClick={() => void onLogout()}
          type="button"
        >
          <LogOut size={14} /> Se déconnecter
        </button>
      </section>
    </main>
  );
}

function SplashScreen({ label = "Chargement…" }: { label?: string }) {
  return (
    <main className="login-screen">
      <section className="login-card loading-card">
        <LoaderCircle size={28} className="spin" />
        <p>{label}</p>
      </section>
    </main>
  );
}

function ErrorScreen({
  message,
  online,
  onRetry,
  onLogout,
}: {
  message: string;
  online: boolean;
  onRetry: () => Promise<void>;
  onLogout: () => Promise<void>;
}) {
  return (
    <main className="login-screen">
      <section className="login-card">
        <div className="brand login-brand">
          <div className="brand-mark">
            <Wallet size={21} />
          </div>
          <span>
            mes<strong>dépenses</strong>
          </span>
        </div>
        <h1>Données indisponibles</h1>
        <p className="login-subtitle">{message}</p>
        {!online && (
          <p className="form-error">
            Aucune donnée n'a encore été synchronisée sur cet appareil.
          </p>
        )}
        <button className="add-button login-submit" onClick={() => void onRetry()}>
          <RefreshCw size={17} /> Réessayer
        </button>
        <button className="text-link" onClick={() => void onLogout()} type="button">
          <LogOut size={14} /> Se déconnecter
        </button>
      </section>
    </main>
  );
}

function EmptyState({ label }: { label: string }) {
  return <p className="empty-state">{label}</p>;
}

function euro(cents: number): string {
  return new Intl.NumberFormat("fr-FR", {
    style: "currency",
    currency: "EUR",
  }).format(cents / 100);
}

function centsToInput(cents: number): string {
  return (cents / 100).toFixed(2);
}

function parseEurosToCents(value: string): number | null {
  const normalized = value.trim().replace(",", ".");
  if (!/^\d+(\.\d{1,2})?$/.test(normalized)) {
    return null;
  }
  const cents = Math.round(Number(normalized) * 100);
  return cents > 0 ? cents : null;
}

function parseSignedEurosToCents(value: string): number | null {
  const normalized = value.trim().replace(",", ".");
  if (!/^-?\d+(\.\d{1,2})?$/.test(normalized)) {
    return null;
  }
  return Math.round(Number(normalized) * 100);
}

function todayISO(): string {
  return new Date().toLocaleDateString("fr-CA");
}

function dateInputToInstant(value: string): string {
  return new Date(`${value}T12:00:00`).toISOString();
}

function formatDate(value: string): string {
  const date = new Date(value.length === 10 ? `${value}T12:00:00` : value);
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "short",
  }).format(date);
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function periodLabel(period: string): string {
  const date = new Date(`${period}-01T12:00:00`);
  const label = new Intl.DateTimeFormat("fr-FR", {
    month: "long",
    year: "numeric",
  }).format(date);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function progress(spent: number, allocated: number): number {
  if (allocated <= 0) {
    return 0;
  }
  return Math.min(100, Math.round((spent / allocated) * 100));
}

function percentageInputValue(value: string): string {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? String(parsed) : value;
}

function percentageFor(
  rule: { members: { user_id: string; percentage: string }[] },
  userId: string,
): string {
  const member = rule.members.find((item) => item.user_id === userId);
  return member ? Number(member.percentage).toFixed(0) : "—";
}

function categoryVisual(name: string): { Icon: LucideIcon; tone: string } {
  const normalized = name.toLowerCase();
  if (normalized.includes("course") || normalized.includes("aliment")) {
    return { Icon: ShoppingBasket, tone: "purple" };
  }
  if (normalized.includes("transport")) {
    return { Icon: Car, tone: "blue" };
  }
  if (normalized.includes("santé") || normalized.includes("sante")) {
    return { Icon: HeartPulse, tone: "rose" };
  }
  if (normalized.includes("loisir") || normalized.includes("sortie")) {
    return { Icon: Coffee, tone: "amber" };
  }
  if (normalized.includes("logement") || normalized.includes("énergie")) {
    return { Icon: House, tone: "violet" };
  }
  return { Icon: Wallet, tone: "blue" };
}

function statusLabel(status: string): string {
  switch (status) {
    case "paid":
      return "Payée";
    case "confirmed":
      return "Montant confirmé";
    case "skipped":
      return "Ignorée";
    default:
      return "À payer";
  }
}

function contributionStatus(status: Contribution["status"]): string {
  switch (status) {
    case "transferred":
      return "Virement effectué";
    case "cancelled":
      return "Annulée";
    default:
      return "À transférer";
  }
}

function sectionDescription(section: Section): string {
  switch (section) {
    case "Dépenses":
      return "Toutes les dépenses accessibles sur le périmètre sélectionné.";
    case "Charges récurrentes":
      return "Échéances à venir et pointage des paiements réels.";
    case "Budget courses":
      return "Enveloppe commune et achats de courses.";
    case "Répartition":
      return "Règle par défaut et contributions du mois.";
    case "Historique":
      return "Transactions enregistrées, tous périmètres accessibles.";
    default:
      return "";
  }
}

function errorMessage(error: unknown): string {
  return error instanceof Error ? error.message : "Opération impossible.";
}

export default App;
