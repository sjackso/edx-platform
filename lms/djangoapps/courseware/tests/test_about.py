"""
Test the about xblock
"""
import datetime
import pytz

from django.conf import settings
from django.core.urlresolvers import reverse
from django.test.utils import override_settings
from mock import patch
from opaque_keys.edx.locations import SlashSeparatedCourseKey

from course_modes.models import CourseMode
from xmodule.modulestore.tests.django_utils import (
    TEST_DATA_MOCK_MODULESTORE, TEST_DATA_MIXED_CLOSED_MODULESTORE
)
from student.models import CourseEnrollment
from student.tests.factories import UserFactory, CourseEnrollmentAllowedFactory
from shoppingcart.models import Order, PaidCourseRegistration
from xmodule.course_module import CATALOG_VISIBILITY_ABOUT, CATALOG_VISIBILITY_NONE
from xmodule.modulestore.tests.django_utils import ModuleStoreTestCase
from xmodule.modulestore.tests.factories import CourseFactory, ItemFactory
from util.milestones_helpers import set_prerequisite_course

from .helpers import LoginEnrollmentTestCase

# HTML for registration button
REG_STR = "<form id=\"class_enroll_form\" method=\"post\" data-remote=\"true\" action=\"/change_enrollment\">"
SHIB_ERROR_STR = "The currently logged-in user account does not have permission to enroll in this course."


@override_settings(MODULESTORE=TEST_DATA_MOCK_MODULESTORE)
class AboutTestCase(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests about xblock.
    """

    def setUp(self):
        self.course = CourseFactory.create()
        self.about = ItemFactory.create(
            category="about", parent_location=self.course.location,
            data="OOGIE BLOOGIE", display_name="overview"
        )
        self.course_without_about = CourseFactory.create(catalog_visibility=CATALOG_VISIBILITY_NONE)
        self.about = ItemFactory.create(
            category="about", parent_location=self.course_without_about.location,
            data="WITHOUT ABOUT", display_name="overview"
        )
        self.course_with_about = CourseFactory.create(catalog_visibility=CATALOG_VISIBILITY_ABOUT)
        self.about = ItemFactory.create(
            category="about", parent_location=self.course_with_about.location,
            data="WITH ABOUT", display_name="overview"
        )

        self.purchase_course = CourseFactory.create(org='MITx', number='buyme', display_name='Course To Buy')
        self.course_mode = CourseMode(course_id=self.purchase_course.id,
                                      mode_slug="honor",
                                      mode_display_name="honor cert",
                                      min_price=10)
        self.course_mode.save()

    def test_anonymous_user(self):
        """
        This test asserts that a non-logged in user can visit the course about page
        """
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("OOGIE BLOOGIE", resp.content)

        # Check that registration button is present
        self.assertIn(REG_STR, resp.content)

    def test_logged_in(self):
        """
        This test asserts that a logged-in user can visit the course about page
        """
        self.setup_user()
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("OOGIE BLOOGIE", resp.content)

    def test_already_enrolled(self):
        """
        Asserts that the end user sees the appropriate messaging
        when he/she visits the course about page, but is already enrolled
        """
        self.setup_user()
        self.enroll(self.course, True)
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("You are registered for this course", resp.content)
        self.assertIn("View Courseware", resp.content)

    @override_settings(COURSE_ABOUT_VISIBILITY_PERMISSION="see_about_page")
    def test_visible_about_page_settings(self):
        """
        Verify that the About Page honors the permission settings in the course module
        """
        url = reverse('about_course', args=[self.course_with_about.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("WITH ABOUT", resp.content)

        url = reverse('about_course', args=[self.course_without_about.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 404)

    @patch.dict(settings.FEATURES, {'ENABLE_MKTG_SITE': True})
    def test_logged_in_marketing(self):
        self.setup_user()
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        # should be redirected
        self.assertEqual(resp.status_code, 302)
        # follow this time, and check we're redirected to the course info page
        resp = self.client.get(url, follow=True)
        target_url = resp.redirect_chain[-1][0]
        info_url = reverse('info', args=[self.course.id.to_deprecated_string()])
        self.assertTrue(target_url.endswith(info_url))

    @patch.dict(settings.FEATURES, {'MILESTONES_APP': True, 'ENABLE_PREREQUISITE_COURSES': True})
    def test_pre_requisite_course(self):
        pre_requisite_course = CourseFactory.create(org='edX', course='900', display_name='pre requisite course')
        set_prerequisite_course(unicode(self.course.id), unicode(pre_requisite_course.id))
        self.setup_user()
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("<span class=\"important-dates-item-text pre-requisite\">{} {}</span>"
                      .format(pre_requisite_course.location.org,
                              pre_requisite_course.location.course),
                      resp.content.strip('\n'))


@override_settings(MODULESTORE=TEST_DATA_MIXED_CLOSED_MODULESTORE)
class AboutTestCaseXML(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Tests for the course about page
    """
    # The following XML test course (which lives at common/test/data/2014)
    # is closed; we're testing that an about page still appears when
    # the course is already closed
    xml_course_id = SlashSeparatedCourseKey('edX', 'detached_pages', '2014')

    # this text appears in that course's about page
    # common/test/data/2014/about/overview.html
    xml_data = "about page 463139"

    @patch.dict('django.conf.settings.FEATURES', {'DISABLE_START_DATES': False})
    def test_logged_in_xml(self):
        self.setup_user()
        url = reverse('about_course', args=[self.xml_course_id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.xml_data, resp.content)

    @patch.dict('django.conf.settings.FEATURES', {'DISABLE_START_DATES': False})
    def test_anonymous_user_xml(self):
        url = reverse('about_course', args=[self.xml_course_id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(self.xml_data, resp.content)


@override_settings(MODULESTORE=TEST_DATA_MOCK_MODULESTORE)
class AboutWithCappedEnrollmentsTestCase(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    This test case will check the About page when a course has a capped enrollment
    """
    def setUp(self):
        """
        Set up the tests
        """
        self.course = CourseFactory.create(metadata={"max_student_enrollments_allowed": 1})

        self.about = ItemFactory.create(
            category="about", parent_location=self.course.location,
            data="OOGIE BLOOGIE", display_name="overview"
        )

    def test_enrollment_cap(self):
        """
        This test will make sure that enrollment caps are enforced
        """
        self.setup_user()
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn('<a href="#" class="register">', resp.content)

        self.enroll(self.course, verify=True)

        # create a new account since the first account is already registered for the course
        self.email = 'foo_second@test.com'
        self.password = 'bar'
        self.username = 'test_second'
        self.create_account(self.username,
                            self.email, self.password)
        self.activate_user(self.email)
        self.login(self.email, self.password)

        # Get the about page again and make sure that the page says that the course is full
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Course is full", resp.content)

        # Try to enroll as well
        result = self.enroll(self.course)
        self.assertFalse(result)

        # Check that registration button is not present
        self.assertNotIn(REG_STR, resp.content)


@override_settings(MODULESTORE=TEST_DATA_MOCK_MODULESTORE)
class AboutWithInvitationOnly(ModuleStoreTestCase):
    """
    This test case will check the About page when a course is invitation only.
    """
    def setUp(self):

        self.course = CourseFactory.create(metadata={"invitation_only": True})

        self.about = ItemFactory.create(
            category="about", parent_location=self.course.location,
            display_name="overview"
        )

    def test_invitation_only(self):
        """
        Test for user not logged in, invitation only course.
        """

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Enrollment in this course is by invitation only", resp.content)

        # Check that registration button is not present
        self.assertNotIn(REG_STR, resp.content)

    def test_invitation_only_but_allowed(self):
        """
        Test for user logged in and allowed to enroll in invitation only course.
        """

        # Course is invitation only, student is allowed to enroll and logged in
        user = UserFactory.create(username='allowed_student', password='test', email='allowed_student@test.com')
        CourseEnrollmentAllowedFactory(email=user.email, course_id=self.course.id)
        self.client.login(username=user.username, password='test')

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn(u"Register for {}".format(self.course.id.course), resp.content)

        # Check that registration button is present
        self.assertIn(REG_STR, resp.content)


@patch.dict(settings.FEATURES, {'RESTRICT_ENROLL_BY_REG_METHOD': True})
@override_settings(MODULESTORE=TEST_DATA_MOCK_MODULESTORE)
class AboutTestCaseShibCourse(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    Test cases covering about page behavior for courses that use shib enrollment domain ("shib courses")
    """
    def setUp(self):
        self.course = CourseFactory.create(enrollment_domain="shib:https://idp.stanford.edu/")

        self.about = ItemFactory.create(
            category="about", parent_location=self.course.location,
            data="OOGIE BLOOGIE", display_name="overview"
        )

    def test_logged_in_shib_course(self):
        """
        For shib courses, logged in users will see the register button, but get rejected once they click there
        """
        self.setup_user()
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("OOGIE BLOOGIE", resp.content)
        self.assertIn(u"Register for {}".format(self.course.id.course), resp.content)
        self.assertIn(SHIB_ERROR_STR, resp.content)
        self.assertIn(REG_STR, resp.content)

    def test_anonymous_user_shib_course(self):
        """
        For shib courses, anonymous users will also see the register button
        """
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("OOGIE BLOOGIE", resp.content)
        self.assertIn(u"Register for {}".format(self.course.id.course), resp.content)
        self.assertIn(SHIB_ERROR_STR, resp.content)
        self.assertIn(REG_STR, resp.content)


@override_settings(MODULESTORE=TEST_DATA_MOCK_MODULESTORE)
class AboutWithClosedEnrollment(ModuleStoreTestCase):
    """
    This test case will check the About page for a course that has enrollment start/end
    set but it is currently outside of that period.
    """
    def setUp(self):

        super(AboutWithClosedEnrollment, self).setUp()
        self.course = CourseFactory.create(metadata={"invitation_only": False})

        # Setup enrollment period to be in future
        now = datetime.datetime.now(pytz.UTC)
        tomorrow = now + datetime.timedelta(days=1)
        nextday = tomorrow + datetime.timedelta(days=1)

        self.course.enrollment_start = tomorrow
        self.course.enrollment_end = nextday
        self.course = self.update_course(self.course, self.user.id)

        self.about = ItemFactory.create(
            category="about", parent_location=self.course.location,
            display_name="overview"
        )

    def test_closed_enrollmement(self):

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Enrollment is Closed", resp.content)

        # Check that registration button is not present
        self.assertNotIn(REG_STR, resp.content)

    def test_course_price_is_not_visble_in_sidebar(self):
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        # course price is not visible ihe course_about page when the course
        # mode is not set to honor
        self.assertNotIn('<span class="important-dates-item-text">$10</span>', resp.content)


@override_settings(MODULESTORE=TEST_DATA_MOCK_MODULESTORE)
@patch.dict(settings.FEATURES, {'ENABLE_SHOPPING_CART': True})
@patch.dict(settings.FEATURES, {'ENABLE_PAID_COURSE_REGISTRATION': True})
class AboutPurchaseCourseTestCase(LoginEnrollmentTestCase, ModuleStoreTestCase):
    """
    This test class runs through a suite of verifications regarding
    purchaseable courses
    """
    def setUp(self):
        super(AboutPurchaseCourseTestCase, self).setUp()
        self.course = CourseFactory.create(org='MITx', number='buyme', display_name='Course To Buy')
        self._set_ecomm(self.course)

    def _set_ecomm(self, course):
        """
        Helper method to turn on ecommerce on the course
        """
        course_mode = CourseMode(
            course_id=course.id,
            mode_slug="honor",
            mode_display_name="honor cert",
            min_price=10,
        )
        course_mode.save()

    def test_anonymous_user(self):
        """
        Make sure an anonymous user sees the purchase button
        """
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Add buyme to Cart ($10)", resp.content)

    def test_logged_in(self):
        """
        Make sure a logged in user sees the purchase button
        """
        self.setup_user()
        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Add buyme to Cart ($10)", resp.content)

    def test_already_in_cart(self):
        """
        This makes sure if a user has this course in the cart, that the expected message
        appears
        """
        self.setup_user()
        cart = Order.get_cart_for_user(self.user)
        PaidCourseRegistration.add_to_order(cart, self.course.id)

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("This course is in your", resp.content)
        self.assertNotIn("Add buyme to Cart ($10)", resp.content)

    def test_already_enrolled(self):
        """
        This makes sure that the already enrolled message appears for paywalled courses
        """
        self.setup_user()

        # note that we can't call self.enroll here since that goes through
        # the Django student views, which doesn't allow for enrollments
        # for paywalled courses
        CourseEnrollment.enroll(self.user, self.course.id)

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])

        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("You are registered for this course", resp.content)
        self.assertIn("View Courseware", resp.content)
        self.assertNotIn("Add buyme to Cart ($10)", resp.content)

    def test_closed_enrollment(self):
        """
        This makes sure that paywalled courses also honor the registration
        window
        """
        self.setup_user()
        now = datetime.datetime.now(pytz.UTC)
        tomorrow = now + datetime.timedelta(days=1)
        nextday = tomorrow + datetime.timedelta(days=1)

        self.course.enrollment_start = tomorrow
        self.course.enrollment_end = nextday
        self.course = self.update_course(self.course, self.user.id)

        url = reverse('about_course', args=[self.course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Enrollment is Closed", resp.content)
        self.assertNotIn("Add buyme to Cart ($10)", resp.content)

        # course price is visible ihe course_about page when the course
        # mode is set to honor and it's price is set
        self.assertIn('<span class="important-dates-item-text">$10</span>', resp.content)

    def test_invitation_only(self):
        """
        This makes sure that the invitation only restirction takes prescendence over
        any purchase enablements
        """
        course = CourseFactory.create(metadata={"invitation_only": True})
        self._set_ecomm(course)
        self.setup_user()

        url = reverse('about_course', args=[course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Enrollment in this course is by invitation only", resp.content)

    def test_enrollment_cap(self):
        """
        Make sure that capped enrollments work even with
        paywalled courses
        """
        course = CourseFactory.create(
            metadata={
                "max_student_enrollments_allowed": 1,
                "display_coursenumber": "buyme",
            }
        )
        self._set_ecomm(course)

        self.setup_user()
        url = reverse('about_course', args=[course.id.to_deprecated_string()])
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Add buyme to Cart ($10)", resp.content)

        # note that we can't call self.enroll here since that goes through
        # the Django student views, which doesn't allow for enrollments
        # for paywalled courses
        CourseEnrollment.enroll(self.user, course.id)

        # create a new account since the first account is already registered for the course
        email = 'foo_second@test.com'
        password = 'bar'
        username = 'test_second'
        self.create_account(username,
                            email, password)
        self.activate_user(email)
        self.login(email, password)

        # Get the about page again and make sure that the page says that the course is full
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        self.assertIn("Course is full", resp.content)
        self.assertNotIn("Add buyme to Cart ($10)", resp.content)
