import logging
from django.conf import settings
from cryptography.fernet import Fernet, InvalidToken

logger = logging.getLogger(__name__)

class FernetKeyError(Exception):
    """Exception levée en cas de clé FERNET_KEY manquante ou invalide."""
    pass


def get_fernet_instance() -> Fernet:
    key = getattr(settings, 'FERNET_KEY', None)
    if not key:
        raise FernetKeyError(
            "La clé de chiffrement FERNET_KEY est introuvable. "
            "Configurez la variable d'environnement FERNET_KEY côté serveur."
        )
    try:
        if isinstance(key, str):
            key = key.encode('utf-8')
        return Fernet(key)
    except Exception as e:
        raise FernetKeyError(f"La clé FERNET_KEY fournie est invalide : {str(e)}")


def encrypt_password(raw_password: str) -> str:
    """Chiffre de manière réversible un mot de passe avec Fernet."""
    if not raw_password:
        return ""
    fernet = get_fernet_instance()
    encrypted_bytes = fernet.encrypt(raw_password.encode('utf-8'))
    return encrypted_bytes.decode('utf-8')


def decrypt_password(encrypted_token: str) -> str:
    """Déchiffre un mot de passe chiffré avec Fernet."""
    if not encrypted_token:
        return ""
    fernet = get_fernet_instance()
    try:
        decrypted_bytes = fernet.decrypt(encrypted_token.encode('utf-8'))
        return decrypted_bytes.decode('utf-8')
    except InvalidToken:
        logger.error("Échec du déchiffrement Fernet : token invalide ou clé corrompue.")
        raise FernetKeyError("Impossible de déchiffrer les identifiants avec la clé courante.")


def matches_rule(rule, title: str, description: str = "") -> bool:
    """
    Évalue si un texte donné correspond à une règle de filtrage.
    Prend en compte le mode de correspondance, le champ cible et la sensibilité à la casse.
    """
    if not rule.keyword:
        return False

    title = title or ""
    description = description or ""

    if rule.target_field == 'title':
        target_text = title.strip()
    else:
        target_text = f"{title} {description}".strip()

    keyword = rule.keyword.strip()

    if not rule.case_sensitive:
        target_text = target_text.lower()
        keyword = keyword.lower()

    if rule.match_mode == 'contains':
        return keyword in target_text
    elif rule.match_mode == 'starts_with':
        return target_text.startswith(keyword)
    elif rule.match_mode == 'ends_with':
        return target_text.endswith(keyword)
    elif rule.match_mode == 'equals':
        return target_text == keyword

    return False


def evaluate_event_for_user(user, event):
    """
    Évalue l'événement par rapport à toutes les règles d'un utilisateur.
    Retourne :
      - is_blacklisted: bool
      - is_favorite: bool
      - matching_rules: list
    """
    rules = user.filter_rules.all()
    matching_rules = []
    is_blacklisted = False
    is_favorite = False

    for rule in rules:
        if matches_rule(rule, event.title, event.description):
            matching_rules.append(rule)
            if rule.rule_type == 'blacklist':
                is_blacklisted = True
            elif rule.rule_type == 'favorite':
                is_favorite = True

    return {
        'is_blacklisted': is_blacklisted,
        'is_favorite': is_favorite,
        'matching_rules': matching_rules,
    }
