from app.questionnaire.location import Location
from app.views.contexts.question import build_question_context
from app.views.handlers.question import Question


class PrimaryPersonQuestion(Question):
    @property
    def parent_location(self):
        return Location(
            section_id=self._current_location.section_id,
            block_id=self.rendered_block["parent_id"],
        )

    def _get_routing_path(self):
        return self.router.routing_path(section_id=self._current_location.section_id)

    def is_location_valid(self):
        return self.router.can_access_location(self.parent_location, self._routing_path)

    def get_previous_location_url(self):
        return self.parent_location.url()

    def get_next_location_url(self):
        return self.router.get_next_location_url(
            self.parent_location, self._routing_path
        )

    def get_context(self):
        return build_question_context(self.rendered_block, self.form)

    def handle_post(self):
        self.questionnaire_store_updater.update_answers(self.form)

        self.questionnaire_store_updater.add_completed_location(
            location=self.parent_location
        )

        self._update_section_completeness(location=self.parent_location)
        self.questionnaire_store_updater.save()
