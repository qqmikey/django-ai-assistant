from django.test import SimpleTestCase

from django_ai_admin.services.intent_router import INTERNAL_APP_LABEL, route_intent


class IntentRouterTests(SimpleTestCase):
    def setUp(self):
        self.manifest = {
            'app.User': ['id', 'username', 'created_at'],
            'app.Payment': ['id', 'user_id', 'amount', 'created_at'],
            f'{INTERNAL_APP_LABEL}.Chat': ['id', 'title', 'created_at'],
            'domain_chat.ChatSession': ['id', 'user_id', 'status', 'created_at'],
            'domain_chat.ChatMessage': ['id', 'session_id', 'role', 'created_at'],
        }

    def test_routes_data_query(self):
        def classifier(**kwargs):
            return {
                'label': 'DATA_QUERY',
                'confidence': 0.91,
                'reason': 'clear_data_request',
                'candidate_models': ['app.User'],
                'normalized_query': kwargs['question'],
            }

        decision = route_intent('How many users registered today?', self.manifest, classifier=classifier)
        self.assertEqual(decision.label, 'DATA_QUERY')
        self.assertEqual(decision.candidate_models, ['app.User'])

    def test_routes_clarification_with_options(self):
        def classifier(**kwargs):
            return {
                'label': 'CLARIFICATION',
                'confidence': 0.66,
                'reason': 'ambiguous_scope',
                'candidate_models': ['app.User', 'app.Payment'],
                'clarification_question': 'Do you mean users or payments?',
                'options': [
                    {'id': '1', 'label': 'app.User', 'model': 'app.User'},
                    {'id': '2', 'label': 'app.Payment', 'model': 'app.Payment'},
                ],
                'normalized_query': kwargs['question'],
            }

        decision = route_intent('Show weekly stats', self.manifest, classifier=classifier)
        self.assertEqual(decision.label, 'CLARIFICATION')
        self.assertEqual(len(decision.options), 2)
        self.assertEqual(decision.options[0]['model'], 'app.User')

    def test_routes_out_of_scope(self):
        def classifier(**kwargs):
            return {
                'label': 'OUT_OF_SCOPE',
                'confidence': 0.88,
                'reason': 'not_project_data',
                'candidate_models': [],
                'normalized_query': kwargs['question'],
            }

        decision = route_intent('Write a poem about ocean', self.manifest, classifier=classifier)
        self.assertEqual(decision.label, 'OUT_OF_SCOPE')

    def test_fallback_on_classifier_error(self):
        def classifier(**kwargs):
            raise RuntimeError('boom')

        decision = route_intent('How many payments today?', self.manifest, classifier=classifier)
        self.assertEqual(decision.label, 'DATA_QUERY')
        self.assertGreaterEqual(decision.confidence, 0.5)

    def test_prioritizes_explicit_app_label_over_internal_chat(self):
        def classifier(**kwargs):
            return {
                'label': 'CLARIFICATION',
                'confidence': 0.71,
                'reason': 'ambiguous_chat',
                'candidate_models': [f'{INTERNAL_APP_LABEL}.Chat'],
                'clarification_question': 'Which chat model do you mean?',
                'options': [{'id': '1', 'label': f'{INTERNAL_APP_LABEL}.Chat', 'model': f'{INTERNAL_APP_LABEL}.Chat'}],
                'normalized_query': kwargs['question'],
            }

        decision = route_intent('I need domain_chat chats count', self.manifest, classifier=classifier)
        self.assertEqual(decision.label, 'CLARIFICATION')
        self.assertTrue(decision.candidate_models)
        self.assertTrue(decision.candidate_models[0].startswith('domain_chat.'))
        self.assertTrue(decision.options)
        self.assertTrue(decision.options[0]['model'].startswith('domain_chat.'))

    def test_demotes_internal_chat_for_generic_chat_query(self):
        def classifier(**kwargs):
            return {
                'label': 'DATA_QUERY',
                'confidence': 0.69,
                'reason': 'generic_chat',
                'candidate_models': [f'{INTERNAL_APP_LABEL}.Chat'],
                'normalized_query': kwargs['question'],
            }

        decision = route_intent('How many chats were created today?', self.manifest, classifier=classifier)
        self.assertEqual(decision.label, 'DATA_QUERY')
        self.assertTrue(decision.candidate_models)
        self.assertTrue(decision.candidate_models[0].startswith('domain_chat.'))
