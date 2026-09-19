import re
import hashlib
from bs4 import BeautifulSoup

def calculate_event_hash(source_id: str, title: str, event_type: str, date_event: str, location: str, description: str) -> str:
    """Calcule une empreinte SHA-256 stable pour détecter toute modification."""
    raw = f"{source_id.strip()}|{title.strip()}|{event_type.strip()}|{date_event.strip()}|{location.strip()}|{description.strip()}"
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()

def parse_events_html(html_content: str, base_url: str = "https://sport.univ-cotedazur.fr"):
    """
    Parse le code HTML de la page des événements UniCA Sport et extrait
    la liste des événements de manière structurée et résiliente.
    """
    soup = BeautifulSoup(html_content, 'html.parser')
    event_cards = soup.select('.card-event')
    parsed_events = []

    for card in event_cards:
        # Extraction de l'ID unique via les modals liés
        source_id = None
        modal_btn = card.select_one('[data-target*="modal_details_event_"], [data-target*="modal_image_event_"]')
        if modal_btn and modal_btn.get('data-target'):
            match = re.search(r'modal_(?:details|image)_event_(\d+)', modal_btn['data-target'])
            if match:
                source_id = match.group(1)

        if not source_id:
            # Fallback : chercher dans les modals imbriqués
            modal = card.select_one('[id*="modal_details_event_"], [id*="modal_image_event_"]')
            if modal and modal.get('id'):
                match = re.search(r'modal_(?:details|image)_event_(\d+)', modal['id'])
                if match:
                    source_id = match.group(1)

        # Extraction du Titre
        title_el = card.select_one('.event-info h2, h2')
        title = title_el.get_text(strip=True) if title_el else "Événement sans titre"

        # Si aucun ID n'a pu être extrait, générer un ID de repli basé sur le titre
        if not source_id:
            source_id = hashlib.md5(title.encode('utf-8')).hexdigest()[:12]

        # Extraction du Type d'événement (ex: Sortie, Tournoi...)
        type_el = card.select_one('.event-info > .row > p, .event-info p')
        event_type = type_el.get_text(strip=True) if type_el else ""

        # Extraction de la Description
        desc_el = card.select_one('.text_evenement_too_long')
        if not desc_el:
            desc_el = card.select_one('.modal-body')
        description = desc_el.get_text(separator="\n", strip=True) if desc_el else ""

        # Extraction du Lieu
        location_el = card.select_one('.event-location p')
        location = location_el.get_text(strip=True) if location_el else ""

        # Extraction des Horaires / Date
        time_el = card.select_one('.event-time p')
        date_event = time_el.get_text(separator=" ", strip=True) if time_el else ""

        # Extraction de l'Encadrant
        supervisor_el = card.select_one('.event-supervisor p')
        supervisor = supervisor_el.get_text(strip=True) if supervisor_el else ""

        # Extraction de l'Image
        image_url = ""
        img_container = card.select_one('.event-img, .event-pic')
        if img_container:
            style = img_container.get('style', '')
            match_url = re.search(r"url\(['\"]?(https?://[^'\")]+)['\"]?\)", style)
            if match_url:
                image_url = match_url.group(1)

        if not image_url:
            img_tag = card.select_one('.modal-body img, [id*="modal_image_event"] img, img.rounded')
            if img_tag and img_tag.get('src'):
                src = img_tag['src']
                if src.startswith('http'):
                    image_url = src
                elif src.startswith('/'):
                    image_url = f"{base_url}{src}"

        # URL de l'événement
        event_url = f"{base_url}/fr/UcaWeb/Evenement#event-{source_id}"

        # Calcul du hash de contenu
        content_hash = calculate_event_hash(
            source_id=source_id,
            title=title,
            event_type=event_type,
            date_event=date_event,
            location=location,
            description=description
        )

        parsed_events.append({
            'source_id': source_id,
            'title': title,
            'event_type': event_type,
            'description': description,
            'date_event': date_event,
            'location': location,
            'supervisor': supervisor,
            'url': event_url,
            'image_url': image_url,
            'content_hash': content_hash,
        })

    return parsed_events
