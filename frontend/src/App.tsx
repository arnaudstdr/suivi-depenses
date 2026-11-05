import { useState } from "react";
import {
  Wallet, LayoutDashboard, ArrowLeftRight, PiggyBank, Repeat2, Scale,
  History, Settings, Bell, Plus, ChevronDown, Search, MoreHorizontal,
  ShoppingBasket, House, Car, HeartPulse, Coffee, ArrowUpRight, ArrowDownRight,
  CalendarDays, Menu, X, Utensils, CircleHelp
} from "lucide-react";

type Context = "Personnel" | "Foyer";
type Section = "Vue d'ensemble" | "Transactions" | "Budgets" | "Récurrences" | "Répartition" | "Historique";

const nav = [
  { label: "Vue d'ensemble" as Section, icon: LayoutDashboard },
  { label: "Transactions" as Section, icon: ArrowLeftRight },
  { label: "Budgets" as Section, icon: PiggyBank },
  { label: "Récurrences" as Section, icon: Repeat2 },
  { label: "Répartition" as Section, icon: Scale },
  { label: "Historique" as Section, icon: History },
];

const transactions = [
  { title: "Courses alimentaires", category: "Alimentation", date: "Aujourd'hui · 09:42", amount: "− 68,40 €", icon: ShoppingBasket, tone: "purple", shared: false },
  { title: "Abonnement transport", category: "Transport", date: "Hier · 18:20", amount: "− 42,00 €", icon: Car, tone: "blue", shared: false },
  { title: "Pharmacie du centre", category: "Santé", date: "3 nov. · 11:15", amount: "− 16,80 €", icon: HeartPulse, tone: "rose", shared: false },
  { title: "Café des Vosges", category: "Sorties", date: "2 nov. · 16:32", amount: "− 8,50 €", icon: Coffee, tone: "amber", shared: false },
];

const budgets = [
  { name: "Alimentation", spent: 186.4, limit: 250, color: "violet" },
  { name: "Transport", spent: 74, limit: 120, color: "blue" },
  { name: "Sorties", spent: 42.5, limit: 80, color: "orange" },
  { name: "Santé", spent: 16.8, limit: 60, color: "green" },
];

function euro(value: number) {
  return new Intl.NumberFormat("fr-FR", { style: "currency", currency: "EUR" }).format(value);
}

function App() {
  const [context, setContext] = useState<Context>("Personnel");
  const [section, setSection] = useState<Section>("Vue d'ensemble");
  const [mobileMenu, setMobileMenu] = useState(false);
  const [showAdd, setShowAdd] = useState(false);
  const isPersonal = context === "Personnel";

  return (
    <div className="app-shell">
      <aside className={`sidebar ${mobileMenu ? "sidebar-open" : ""}`}>
        <div className="brand"><div className="brand-mark"><Wallet size={21}/></div><span>mes<strong>dépenses</strong></span><button className="icon-btn close-menu" onClick={() => setMobileMenu(false)} aria-label="Fermer"><X size={19}/></button></div>
        <div className="workspace-label">ESPACE</div>
        <div className="context-switch">
          <div className="avatar">{isPersonal ? "A" : "F"}</div>
          <div className="context-copy"><strong>{isPersonal ? "Mon espace" : "Notre foyer"}</strong><span>{isPersonal ? "Vue personnelle" : "Vue partagée"}</span></div>
          <ChevronDown size={16} className="muted"/>
          <select aria-label="Changer de contexte" value={context} onChange={e => setContext(e.target.value as Context)}>
            <option>Personnel</option><option>Foyer</option>
          </select>
        </div>
        <nav className="main-nav">
          <div className="nav-caption">GESTION</div>
          {nav.map(item => { const Icon = item.icon; return <button key={item.label} className={`nav-item ${section === item.label ? "active" : ""}`} onClick={() => { setSection(item.label); setMobileMenu(false); }}><Icon size={18}/><span>{item.label}</span>{item.label === "Transactions" && <span className="nav-count">12</span>}</button>; })}
        </nav>
        <div className="sidebar-bottom">
          <button className="nav-item"><Settings size={18}/><span>Paramètres</span></button>
          <div className="profile"><div className="avatar avatar-small">A</div><div><strong>Arnaud</strong><span>Compte personnel</span></div><MoreHorizontal size={18} className="muted"/></div>
        </div>
      </aside>

      {mobileMenu && <button className="mobile-scrim" onClick={() => setMobileMenu(false)} aria-label="Fermer le menu"/>}

      <main className="main-area">
        <header className="topbar">
          <button className="icon-btn mobile-menu-btn" onClick={() => setMobileMenu(true)} aria-label="Ouvrir le menu"><Menu size={21}/></button>
          <div className="breadcrumb"><span>Mon espace</span><span className="crumb-sep">/</span><strong>{section}</strong></div>
          <div className="top-actions"><div className="period"><CalendarDays size={16}/><span>Novembre 2026</span><ChevronDown size={14}/></div><button className="icon-btn notification-btn" aria-label="Notifications"><Bell size={19}/><i/></button><button className="add-button" onClick={() => setShowAdd(true)}><Plus size={18}/> <span>Ajouter une dépense</span></button></div>
        </header>

        {section === "Vue d'ensemble" ? (
          <div className="page-content">
            <div className="page-heading"><div><div className="eyebrow">JEUDI 5 NOVEMBRE 2026</div><h1>Bonjour Arnaud</h1><p>Voici le résumé de tes finances personnelles.</p></div><button className="outline-button"><CalendarDays size={16}/> Ce mois-ci <ChevronDown size={14}/></button></div>
            <section className="summary-grid">
              <article className="summary-card primary-card"><div className="card-top"><span>Dépenses du mois</span><span className="card-icon"><ArrowDownRight size={18}/></span></div><div className="big-number">684,70 €</div><div className="card-foot"><span className="trend negative"><ArrowUpRight size={14}/> 8,2 %</span><span>vs mois dernier</span></div><div className="primary-decoration"/></article>
              <article className="summary-card"><div className="card-top"><span>Budgets consommés</span><span className="soft-icon violet"><PiggyBank size={18}/></span></div><div className="big-number dark-number">319,70 € <small>/ 510 €</small></div><div className="progress-track"><span className="progress-fill violet-fill" style={{width:"62.7%"}}/></div><div className="card-foot"><span>62,7 % utilisé</span><strong>190,30 € restants</strong></div></article>
              <article className="summary-card"><div className="card-top"><span>Transactions</span><span className="soft-icon blue"><ArrowLeftRight size={18}/></span></div><div className="big-number dark-number">24</div><div className="card-foot"><span>Ce mois-ci</span><strong className="positive">+ 3 vs octobre</strong></div><div className="mini-bars"><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/><i/></div></article>
            </section>

            <section className="content-grid">
              <article className="panel budget-panel"><div className="panel-heading"><div><h2>Mes budgets</h2><p>Suivi de tes enveloppes mensuelles</p></div><button className="text-link" onClick={() => setSection("Budgets")}>Tout voir <ArrowUpRight size={15}/></button></div><div className="budget-list">{budgets.map(b => <div className="budget-row" key={b.name}><div className={`budget-symbol ${b.color}`}>{b.name === "Alimentation" ? <ShoppingBasket size={17}/> : b.name === "Transport" ? <Car size={17}/> : b.name === "Sorties" ? <Coffee size={17}/> : <HeartPulse size={17}/>}</div><div className="budget-info"><div className="budget-line"><strong>{b.name}</strong><span>{euro(b.spent)} <small>/ {euro(b.limit)}</small></span></div><div className="progress-track"><span className={`progress-fill ${b.color}-fill`} style={{width:`${Math.min(100,b.spent/b.limit*100)}%`}}/></div></div><span className="budget-percent">{Math.round(b.spent/b.limit*100)}%</span></div>)}</div></article>

              <article className="panel chart-panel"><div className="panel-heading"><div><h2>Répartition des dépenses</h2><p>Par catégorie · Novembre 2026</p></div><button className="icon-btn"><MoreHorizontal size={19}/></button></div><div className="chart-wrap"><div className="donut"><div className="donut-center"><strong>684,70 €</strong><span>Total dépensé</span></div></div><div className="legend"><div><i className="dot d-violet"/><span>Alimentation</span><strong>32 %</strong></div><div><i className="dot d-blue"/><span>Transport</span><strong>24 %</strong></div><div><i className="dot d-orange"/><span>Logement</span><strong>21 %</strong></div><div><i className="dot d-green"/><span>Autres</span><strong>23 %</strong></div></div></div></article>
            </section>

            <section className="content-grid lower-grid">
              <article className="panel transactions-panel"><div className="panel-heading"><div><h2>Dernières transactions</h2><p>Tes opérations récentes</p></div><button className="text-link" onClick={() => setSection("Transactions")}>Voir tout <ArrowUpRight size={15}/></button></div><div className="transaction-list">{transactions.map((t,i) => {const Icon=t.icon;return <div className="transaction-row" key={t.title}><div className={`transaction-symbol ${t.tone}`}><Icon size={17}/></div><div className="transaction-main"><strong>{t.title}</strong><span>{t.category} · {t.date}</span></div><strong className="transaction-amount">{t.amount}</strong></div>;})}</div></article>
              <article className="panel upcoming-panel"><div className="panel-heading"><div><h2>À venir</h2><p>Prochaines dépenses prévues</p></div><button className="icon-btn"><MoreHorizontal size={19}/></button></div><div className="upcoming-item"><div className="date-tile"><strong>08</strong><span>NOV</span></div><div className="upcoming-copy"><strong>Assurance habitation</strong><span>Prélèvement automatique</span></div><strong>− 24,90 €</strong></div><div className="upcoming-item"><div className="date-tile"><strong>12</strong><span>NOV</span></div><div className="upcoming-copy"><strong>Abonnement internet</strong><span>Montant confirmé</span></div><strong>− 39,99 €</strong></div><div className="upcoming-note"><CircleHelp size={15}/> Prévisions indicatives, non encore débitées.</div></article>
            </section>
            <div className="dashboard-footer"><span>Données fictives · Maquette UX</span><span>Dernière synchronisation : aujourd'hui à 09:42</span></div>
          </div>
        ) : (
          <div className="page-content placeholder-page"><div className="page-heading"><div><div className="eyebrow">ESPACE PERSONNEL</div><h1>{section}</h1><p>Cette vue sera détaillée dans la prochaine étape de la maquette.</p></div></div><div className="panel placeholder-panel"><div className="placeholder-icon"><LayoutDashboard size={28}/></div><h2>{section}</h2><p>Écran de démonstration en cours de conception.</p><button className="outline-button" onClick={() => setSection("Vue d'ensemble")}>Retour au tableau de bord</button></div></div>
        )}
      </main>

      <nav className="mobile-bottom-nav">
        {nav.slice(0,4).map(item => {const Icon=item.icon;return <button key={item.label} className={section===item.label?"selected":""} onClick={()=>setSection(item.label)}><Icon size={19}/><span>{item.label==="Vue d'ensemble"?"Accueil":item.label==="Transactions"?"Opérations":item.label}</span></button>;})}
      </nav>

      {showAdd && <div className="modal-backdrop" onClick={() => setShowAdd(false)}><div className="modal" onClick={e=>e.stopPropagation()}><div className="modal-heading"><div><h2>Nouvelle dépense</h2><p>Ajoute une opération à ton espace personnel.</p></div><button className="icon-btn" onClick={() => setShowAdd(false)}><X size={19}/></button></div><label>Libellé<input placeholder="Ex. Courses alimentaires"/></label><div className="form-two"><label>Montant (€)<input type="number" placeholder="0,00"/></label><label>Date<input type="date" defaultValue="2026-11-05"/></label></div><label>Catégorie<select defaultValue="Alimentation"><option>Alimentation</option><option>Transport</option><option>Logement</option><option>Santé</option><option>Loisirs</option></select></label><div className="modal-actions"><button className="outline-button" onClick={() => setShowAdd(false)}>Annuler</button><button className="add-button" onClick={() => setShowAdd(false)}>Enregistrer la dépense</button></div><p className="demo-disclaimer">Maquette : aucune donnée n'est enregistrée.</p></div></div>}
    </div>
  );
}
export default App;