import argparse
import getpass
import sys

from pydantic import EmailStr, TypeAdapter, ValidationError

from app.core.config import get_settings
from app.core.errors import AppError
from app.domains.households.service import HouseholdService
from app.infrastructure.db.session import build_engine, build_session_factory


def _parse_email(value: str) -> str:
    return str(TypeAdapter(EmailStr).validate_python(value)).lower()


def _bootstrap(args: argparse.Namespace) -> int:
    settings = get_settings()
    password = args.password
    if password is None:
        password = getpass.getpass("Mot de passe : ")
        confirmation = getpass.getpass("Confirmer le mot de passe : ")
        if password != confirmation:
            print("Erreur : les mots de passe ne correspondent pas.", file=sys.stderr)
            return 1

    email = _parse_email(args.email)
    engine = build_engine(settings)
    session_factory = build_session_factory(engine)
    try:
        with session_factory() as session:
            user, household, _ = HouseholdService(session, settings).bootstrap(
                email=email,
                first_name=args.first_name,
                household_name=args.household_name,
                password=password,
            )
    finally:
        engine.dispose()

    print(f"Foyer créé : {household.name} ({household.id})")
    print(f"Propriétaire créé : {user.email} ({user.id})")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli")
    subparsers = parser.add_subparsers(dest="command", required=True)

    bootstrap_parser = subparsers.add_parser(
        "bootstrap",
        help="Créer le foyer et le premier compte propriétaire",
    )
    bootstrap_parser.add_argument("--email", required=True)
    bootstrap_parser.add_argument("--first-name", required=True)
    bootstrap_parser.add_argument("--household-name", required=True)
    bootstrap_parser.add_argument(
        "--password",
        help="Mot de passe (déconseillé en ligne de commande, préférer la saisie interactive)",
    )
    bootstrap_parser.set_defaults(handler=_bootstrap)

    args = parser.parse_args(argv)

    try:
        return int(args.handler(args))
    except (AppError, ValueError, ValidationError) as exc:
        message = exc.message if isinstance(exc, AppError) else str(exc)
        print(f"Erreur : {message}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
