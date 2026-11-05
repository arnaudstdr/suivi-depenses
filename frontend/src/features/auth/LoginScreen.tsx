import { FormEvent, useState } from "react";
import { LogIn, Wallet } from "lucide-react";

type LoginScreenProps = {
  online: boolean;
  error: string | null;
  onSubmit: (email: string, password: string) => Promise<void>;
};

export function LoginScreen({ online, error, onSubmit }: LoginScreenProps) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!online || submitting) {
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(email, password);
    } catch {
      // L'erreur est affichée par le parent via la session.
    } finally {
      setSubmitting(false);
    }
  }

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
        <h1>Connexion</h1>
        <p className="login-subtitle">
          Accède à ton espace personnel et au suivi du foyer.
        </p>
        {!online && (
          <p className="form-error" role="status">
            Hors ligne : la connexion nécessite une première synchronisation.
          </p>
        )}
        {error && (
          <p className="form-error" role="alert">
            {error}
          </p>
        )}
        <form onSubmit={handleSubmit}>
          <label>
            Adresse email
            <input
              type="email"
              autoComplete="username"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              required
            />
          </label>
          <label>
            Mot de passe
            <input
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              required
            />
          </label>
          <button
            className="add-button login-submit"
            type="submit"
            disabled={!online || submitting}
          >
            <LogIn size={17} />
            {submitting ? "Connexion…" : "Se connecter"}
          </button>
        </form>
        <p className="demo-disclaimer">
          Les données déjà synchronisées restent consultables hors ligne.
        </p>
      </section>
    </main>
  );
}
