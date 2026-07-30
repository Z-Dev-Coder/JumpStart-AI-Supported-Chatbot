from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from .models import ChatSession, ChatMessage

User = get_user_model()


class ChatAPITestCase(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = User.objects.create_user(
            username='testuser', password='testpass123', email='test@example.com'
        )
        self.other_user = User.objects.create_user(
            username='otheruser', password='testpass123', email='other@example.com'
        )

    def _auth(self, user=None):
        """Authenticate the client with JWT for the given user."""
        from rest_framework_simplejwt.tokens import AccessToken
        u = user or self.user
        token = str(AccessToken.for_user(u))
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {token}')

    # ── Authentication guard ──────────────────────────────────────────────────

    def test_guest_cannot_create_session(self):
        """Unauthenticated request to /api/chat/sessions/new/ returns 401."""
        res = self.client.post('/api/chat/sessions/new/', format='json')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_guest_cannot_list_sessions(self):
        """Unauthenticated request to /api/chat/sessions/ returns 401."""
        res = self.client.get('/api/chat/sessions/')
        self.assertEqual(res.status_code, status.HTTP_401_UNAUTHORIZED)

    # ── Session creation ──────────────────────────────────────────────────────

    def test_authenticated_user_can_create_session(self):
        """POST /api/chat/sessions/new/ creates a new session and returns session_id."""
        self._auth()
        res = self.client.post('/api/chat/sessions/new/', format='json')
        self.assertIn(res.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        self.assertIn('session_id', res.data)
        session_id = res.data['session_id']
        self.assertTrue(ChatSession.objects.filter(id=session_id, customer=self.user).exists())

    def test_session_belongs_to_authenticated_user(self):
        """Created session is owned by the requesting user."""
        self._auth()
        res = self.client.post('/api/chat/sessions/new/', format='json')
        self.assertIn(res.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])
        session = ChatSession.objects.get(id=res.data['session_id'])
        self.assertEqual(session.customer, self.user)

    def test_session_starts_in_ai_active_state(self):
        """New sessions start with state = AI_ACTIVE."""
        self._auth()
        res = self.client.post('/api/chat/sessions/new/', format='json')
        session = ChatSession.objects.get(id=res.data['session_id'])
        self.assertEqual(session.state, ChatSession.State.AI_ACTIVE)

    # ── Message listing ───────────────────────────────────────────────────────

    def test_authenticated_user_can_list_messages(self):
        """GET /api/chat/sessions/<id>/messages/ returns 200 with empty list."""
        self._auth()
        session = ChatSession.objects.create(customer=self.user)
        res = self.client.get(f'/api/chat/sessions/{session.id}/messages/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        messages = data.get('results', data) if isinstance(data, dict) else data
        self.assertIsInstance(messages, list)

    def test_user_cannot_read_other_users_messages(self):
        """User cannot access another user's chat session messages — returns 404."""
        self._auth(self.other_user)
        session = ChatSession.objects.create(customer=self.user)
        res = self.client.get(f'/api/chat/sessions/{session.id}/messages/')
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    def test_message_order_is_chronological(self):
        """Messages are returned oldest-first."""
        self._auth()
        session = ChatSession.objects.create(customer=self.user)
        m1 = ChatMessage.objects.create(session=session, sender='customer', content='First')
        m2 = ChatMessage.objects.create(session=session, sender='ai', content='Second')
        res = self.client.get(f'/api/chat/sessions/{session.id}/messages/')
        data = res.data
        messages = data.get('results', data) if isinstance(data, dict) else data
        self.assertEqual(messages[0]['content'], 'First')
        self.assertEqual(messages[1]['content'], 'Second')

    # ── Cross-session isolation ───────────────────────────────────────────────

    def test_user_only_sees_own_sessions(self):
        """Session list only returns the requesting user's sessions."""
        self._auth()
        own_session = ChatSession.objects.create(customer=self.user)
        other_session = ChatSession.objects.create(customer=self.other_user)
        res = self.client.get('/api/chat/sessions/')
        self.assertEqual(res.status_code, status.HTTP_200_OK)
        data = res.data
        sessions = data.get('results', data) if isinstance(data, dict) else data
        session_ids = [str(s['id']) for s in sessions]
        self.assertIn(str(own_session.id), session_ids)
        self.assertNotIn(str(other_session.id), session_ids)

    # ── Feedback ─────────────────────────────────────────────────────────────

    def test_authenticated_user_can_submit_feedback(self):
        """POST /api/chat/sessions/<id>/feedback/ returns 200/201."""
        self._auth()
        session = ChatSession.objects.create(customer=self.user)
        res = self.client.post(
            f'/api/chat/sessions/{session.id}/feedback/',
            data={'rating': 'positive', 'reason': ''},
            format='json'
        )
        self.assertIn(res.status_code, [status.HTTP_200_OK, status.HTTP_201_CREATED])

    def test_user_cannot_submit_feedback_for_other_session(self):
        """User cannot submit feedback for another user's session."""
        self._auth(self.other_user)
        session = ChatSession.objects.create(customer=self.user)
        res = self.client.post(
            f'/api/chat/sessions/{session.id}/feedback/',
            data={'rating': 'positive'},
            format='json'
        )
        self.assertIn(res.status_code, [status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND])

    # ── Message send (HTTP fallback) ──────────────────────────────────────────

    def test_empty_message_rejected(self):
        """Sending an empty message returns 400."""
        self._auth()
        session = ChatSession.objects.create(customer=self.user)
        res = self.client.post(
            f'/api/chat/sessions/{session.id}/send/',
            data={'content': '   '},
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)

    def test_message_too_long_rejected(self):
        """Sending a message over 2000 chars returns 400."""
        self._auth()
        session = ChatSession.objects.create(customer=self.user)
        res = self.client.post(
            f'/api/chat/sessions/{session.id}/send/',
            data={'content': 'x' * 2001},
            format='json'
        )
        self.assertEqual(res.status_code, status.HTTP_400_BAD_REQUEST)
