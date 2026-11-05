# Frontend — Suivi des dépenses

Application React 18 / Vite connectée à l'API FastAPI, avec support PWA et
consultation hors ligne en lecture seule.

## Commandes disponibles

```bash
npm install
npm run dev
npm run typecheck
npm run test
npm run build
npm run preview
```

Le proxy Vite transmet `/api` et `/health` à `http://127.0.0.1:8000` en
développement et en prévisualisation.

## Session et cache privé

- La session utilise les cookies `HttpOnly` du backend et le jeton CSRF
  double-submit.
- Les réponses GET déjà consultées sont conservées dans un cache applicatif
  privé, nommé par identifiant utilisateur, avec un TTL de 24 h.
- Le cache est purgé à la déconnexion, à l'expiration de session et au
  changement de compte.
- Hors ligne, l'interface est en lecture seule : les mutations sont
  désactivées et aucune file d'écritures différées n'est créée.

## PWA

- `vite-plugin-pwa` génère le manifest et le service worker.
- Le service worker précache uniquement les ressources statiques et le shell.
- Aucune réponse `/api/v1` n'est mise en cache par le service worker.
- Les icônes sont générées par `python3 scripts/generate-icons.py`.

## Tests

`npm run test` exécute Vitest :

- isolation et purge du cache privé ;
- stratégie réseau d'abord avec repli sur cache ;
- parcours de connexion, affichage du dashboard réel et passage en lecture
  seule hors ligne.
