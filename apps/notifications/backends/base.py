from abc import ABC, abstractmethod

class NotificationBackend(ABC):
    """
    Interface commune d'envoi de notification abstraite.
    Chaque canal implémente cette interface.
    """
    @abstractmethod
    def send(self, user, event, message: str, attempt=None) -> bool:
        """
        Envoie la notification à l'utilisateur pour l'événement donné.
        :param user: Instance de CustomUser
        :param event: Instance de Event
        :param message: Message personnalisé ou descriptif
        :param attempt: Optionnel, instance de RegistrationAttempt
        :return: bool indiquant le succès ou l'échec de l'envoi
        """
        pass
