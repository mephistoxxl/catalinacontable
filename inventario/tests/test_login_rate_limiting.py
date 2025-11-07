from datetime import timedelta

from axes.handlers.proxy import AxesProxyHandler
from axes.utils import reset
from django.contrib.auth import get_user_model
from django.contrib.messages import get_messages
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(
    AXES_ENABLED=True,
    AXES_FAILURE_LIMIT=2,
    AXES_COOLOFF_TIME=timedelta(minutes=1),
)
class LoginRateLimitingTests(TestCase):
    def setUp(self):
        reset()
        self.user = get_user_model().objects.create_user(
            username='0123456789012', password='correct-password'
        )
        self.login_url = reverse('inventario:login')

    def tearDown(self):
        reset()

    def _post_login(self, password):
        return self.client.post(
            self.login_url,
            {'identificacion': self.user.username, 'password': password},
            follow=True,
        )

    def _messages_from(self, response):
        return [message.message for message in get_messages(response.wsgi_request)]

    def test_block_message_after_exceeding_limit(self):
        first_response = self._post_login('wrong-password')
        self.assertIn('Usuario o contraseña incorrectos', self._messages_from(first_response))

        response = self._post_login('wrong-password')
        messages = self._messages_from(response)
        self.assertTrue(
            any('Hemos bloqueado temporalmente el acceso' in message for message in messages),
            'Se esperaba mensaje de bloqueo tras múltiples intentos fallidos.',
        )
        self.assertTrue(
            AxesProxyHandler.is_locked(
                response.wsgi_request, credentials={'username': self.user.username}
            )
        )

    def test_locked_user_cannot_login_with_correct_password(self):
        self._post_login('wrong-password')
        self._post_login('wrong-password')

        response = self._post_login('correct-password')
        messages = self._messages_from(response)
        self.assertTrue(
            any('Hemos bloqueado temporalmente el acceso' in message for message in messages),
            'El mensaje de bloqueo debe mostrarse incluso con credenciales válidas.',
        )
        self.assertNotIn('_auth_user_id', self.client.session)
