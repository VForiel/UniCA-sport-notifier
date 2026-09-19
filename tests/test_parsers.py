from django.test import TestCase
from apps.scraping.parsers import parse_events_html, calculate_event_hash

SAMPLE_HTML = """
<div class="card-event">
  <div class="event-pic" data-target="#modal_details_event_980"></div>
  <div class="event-info">
    <div class="row">
      <h2>KAYAK</h2>
      <p>Sortie</p>
      <div class="text_evenement_too_long">Rdv 10h au gymnase VALROSE. Savoir nager.</div>
    </div>
    <div class="event-location"><p>exterieur</p></div>
    <div class="event-time"><p>20/09/2026 10:00</p></div>
    <div class="event-supervisor"><p>aucun encadrant</p></div>
  </div>
</div>

<div class="card-event">
  <div class="event-pic" data-target="#modal_details_event_1014"></div>
  <div class="event-info">
    <div class="row">
      <h2>Stand UP/Paddle</h2>
      <p>Sortie</p>
      <div class="text_evenement_too_long">Sortie ludique en Stand up paddle gonflable.</div>
    </div>
    <div class="event-location"><p>exterieur</p></div>
    <div class="event-time"><p>22/09/2026 08:30</p></div>
    <div class="event-supervisor"><p>aucun encadrant</p></div>
  </div>
</div>
"""

class ParserTests(TestCase):
    def test_parse_sample_events(self):
        events = parse_events_html(SAMPLE_HTML)
        self.assertEqual(len(events), 2)

        kayak = events[0]
        self.assertEqual(kayak['source_id'], "980")
        self.assertEqual(kayak['title'], "KAYAK")
        self.assertEqual(kayak['event_type'], "Sortie")
        self.assertEqual(kayak['location'], "exterieur")
        self.assertIn("10:00", kayak['date_event'])
        self.assertIn("Savoir nager", kayak['description'])
        self.assertTrue(len(kayak['content_hash']) == 64)

        paddle = events[1]
        self.assertEqual(paddle['source_id'], "1014")
        self.assertEqual(paddle['title'], "Stand UP/Paddle")

    def test_content_hash_stability(self):
        h1 = calculate_event_hash("980", "KAYAK", "Sortie", "20/09/2026", "exterieur", "Desc")
        h2 = calculate_event_hash("980", "KAYAK", "Sortie", "20/09/2026", "exterieur", "Desc")
        h3 = calculate_event_hash("980", "KAYAK", "Sortie", "20/09/2026", "exterieur", "Desc modifiée")

        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)

    def test_extract_next_page_url_with_active_button(self):
        from apps.scraping.parsers import extract_next_page_url
        html_page1 = """
        <div class="pagination">
          <button class="btn btn-info disabled">PRÉCÉDENT</button>
          <a class="p-2 pagination-link" href="/fr/UcaWeb/Evenement"><span class="active">1</span></a>
          <a class="p-2 pagination-link" href="/fr/UcaWeb/Evenement/2"><span>2</span></a>
          <a href="/fr/UcaWeb/Evenement/2"><button class="btn btn-primary">SUIVANT</button></a>
        </div>
        """
        next_url = extract_next_page_url(html_page1)
        self.assertEqual(next_url, "https://sport.univ-cotedazur.fr/fr/UcaWeb/Evenement/2")

    def test_extract_next_page_url_with_disabled_button(self):
        from apps.scraping.parsers import extract_next_page_url
        html_page2 = """
        <div class="pagination">
          <a href="/fr/UcaWeb/Evenement"><button class="btn btn-primary">PRÉCÉDENT</button></a>
          <a class="p-2 pagination-link" href="/fr/UcaWeb/Evenement"><span>1</span></a>
          <a class="p-2 pagination-link" href="/fr/UcaWeb/Evenement/2"><span class="active">2</span></a>
          <button class="btn btn-info disabled">SUIVANT</button>
        </div>
        """
        next_url = extract_next_page_url(html_page2)
        self.assertIsNone(next_url)

    def test_extract_next_page_url_without_pagination(self):
        from apps.scraping.parsers import extract_next_page_url
        html_empty = "<div><p>Pas de pagination</p></div>"
        next_url = extract_next_page_url(html_empty)
        self.assertIsNone(next_url)
