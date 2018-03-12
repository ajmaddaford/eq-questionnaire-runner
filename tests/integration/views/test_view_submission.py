import mock

from tests.integration.integration_test_case import IntegrationTestCase


class TestViewSubmission(IntegrationTestCase):

    def setUp(self):
        super().SetUpWithDynamoDB()

    def test_view_submission(self):
        self.launchSurvey('test', 'view_submitted_response')

        # check we're on first page
        self.assertInPage('What is your favourite breakfast food')

        # We fill in our answer
        form_data = {
            # Food choice
            'radio-answer': 'Bacon',
        }

        # We submit the form
        self.post(form_data)

        # check we're on second page
        self.assertInPage('Please enter test values (none mandatory)')

        # We fill in our answers
        form_data = {
            # Food choice
            'test-currency': '12',
            'square-kilometres': '345',
            'test-decimal': '67.89',
        }

        # We submit the form
        self.post(form_data)

        # There are no validation errors
        self.assertInUrl('summary')

        # check we're on the review answers page
        self.assertInPage('Please check your answers carefully before submitting.')

        # Submit answers
        with mock.patch('app.data_model.submitted_responses.put_item',
                        return_value={'ResponseMetadata': {'HTTPStatusCode': 200}}) as put_item:
            self.post(action=None)

            item = put_item.call_args[0][0]

        # check we're on the thank you page and view submission link is available
        self.assertInUrl('thank-you')
        self.assertInPage('View and print a copy of your answers')

        # go to the view submission page
        with mock.patch('app.data_model.submitted_responses.get_item',
                        return_value=item):
            self.get('questionnaire/test/view_submitted_response/view-submission')

        # check we're on the view submission page
        self.assertInUrl('view-submission')
        self.assertInPage('Submitted answers')

        # check answers are on page
        self.assertStatusOK()
        self.assertInPage('Bacon')
        self.assertInPage('12')
        self.assertInPage('345')
        self.assertInPage('67.89')

        # check edit links are not on page
        self.assertNotInPage('data-ga-action="Edit click"')

    def test_try_view_submission_when_not_available(self):
        self.launchSurvey('test', 'currency')

        # check we're on first page
        self.assertInPage('Currency Input Test')

        # We fill in our answers
        form_data = {
            # Food choice
            'answer': '12',
            'answer-usd': '345',
            'answer-eur': '67.89',
            'answer-jpy': '0',
        }

        # We submit the form
        self.post(form_data)

        # There are no validation errors
        self.assertInUrl('summary')

        # Submit answers
        self.post(action=None)

        # check we're on the thank you page and view submission link is not available
        self.assertInUrl('thank-you')
        self.assertNotInPage('View and print a copy of your answers')

        # try go to the view submission page anyway
        self.get('questionnaire/test/currency/view-submission')

        # check we're redirected back to thank you page
        self.assertInUrl('thank-you')

    def test_try_view_submission_early(self):
        self.launchSurvey('test', 'view_submitted_response')

        # check we're on first page
        self.assertInPage('What is your favourite breakfast food')

        # try to get the view-submission page
        self.get('questionnaire/test/view_submitted_response/view-submission')

        # check we're redirected back to first page
        self.assertInPage('What is your favourite breakfast food')
