"""
Course Schedule and Details Settings page.
"""

from .course_page import CoursePage
from bok_choy.promise import EmptyPromise


class SettingsPage(CoursePage):
    """
    Course Schedule and Details Settings page.
    """

    url_path = "settings/details"

    def is_browser_on_page(self):
        return self.q(css='body.view-settings').present

    @property
    def pre_requisite_course(self):
        """
        Returns the pre-requisite course drop down field.
        """
        return self.q(css='#pre-requisite-course')

    def save_changes(self):
        """
        Wait for save changes button to appear and then click it
        """
        EmptyPromise(
            lambda: self.q(css=".action-save").is_present(),
            "Save changes button is visible"
        ).fulfill()
        self.q(css=".action-save").first.click()
        self.wait_for_ajax()
