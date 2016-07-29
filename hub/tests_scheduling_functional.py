import json
from datetime import datetime

from mixer.backend.django import mixer

import lessons.models as lessons
from elk.utils.testing import ClientTestCase, create_customer, create_teacher, mock_request
from hub.models import Class
from teachers.models import WorkingHours
from timeline.models import Entry as TimelineEntry

from . import views


class SchedulingPopupTestCaseBase(ClientTestCase):
    fixtures = ('lessons',)

    def setUp(self):
        self.customer = create_customer()
        self.host = create_teacher()
        mixer.blend(WorkingHours, teacher=self.host, weekday=0, start='13:00', end='15:00')  # monday
        super().setUp()

    def _buy_a_lesson(self, lesson):
        c = Class(
            customer=self.customer,
            lesson=lesson
        )
        c.request = mock_request(self.customer)
        c.save()
        return c

    def _get_step1(self):
        request = self.factory.get('/hub/schedule/step1/')
        request.user = self.customer.user
        return views.step1(request)

    def _step2(self, view, just_checking=False, **kwargs):
        url = '/hub/schedule/step2/'
        if just_checking:
            url = url + '?check'

        request = self.factory.get(url)
        request.user = self.customer.user
        response = view(request, teacher=self.host.pk, **kwargs)

        self.assertIn(response.status_code, (200, 302))
        if len(response.content):
            return json.loads(response.content.decode('utf-8'))


class TestSchedulingPopupHTML(SchedulingPopupTestCaseBase):

    def test_lesson_categories(self):
        """
        Buy two lessons of different type and assure that filter of two types
        has appeared in the scheduling popup.
        """
        self._buy_a_lesson(lessons.OrdinaryLesson.get_default())
        self._buy_a_lesson(mixer.blend(lessons.MasterClass, host=self.host))
        self.assertEquals(self.customer.classes.count(), 2)

        response = self._get_step1()
        with self.assertHTML(response, '.schedule-popup__filters .lesson_type label') as categories:
            self.assertEquals(len(categories), 2)  # user has only two lessons bought — Ordinary lesson and a Master class
            for category in categories:
                self.assertIn(int(category.find('input').attrib.get('value')), [lessons.OrdinaryLesson.contenttype().pk, lessons.MasterClass.contenttype().pk])  # every value of checkbox should be an allowed contenttype
                self.assertIn(category.find('input').attrib.get('data-query-type'), ['lessons', 'teachers'])  # should have both types, because we have bought two lessons — ordinary (not requiring a planned timeline entry, and a master class)
                self.assertNotEqual(len(category.text_content()), 0)  # every lesson type should have a NAME, like <label><input type=radio value="1">NAME</label>.

    def test_popup_without_bought_lessons(self):
        """
        Request a scheduling popup for user without bought classes.
        """
        response = self._get_step1()
        self.assertEquals(response.status_code, 200)  # should not throw anything

    def test_date_selector(self):
        """
        Test date filter — it should exist and have 7 days to select
        """
        self._buy_a_lesson(lessons.OrdinaryLesson.get_default())
        response = self._get_step1()
        with self.assertHTML(response, '.schedule-popup__date-selector select') as (date_selector,):
            options = [i for i in date_selector.findall('option')]
            self.assertEquals(len(options), 7)  # popup has 7 days forward to select


class TestSchedulingPopupAPI(SchedulingPopupTestCaseBase):
    """
    Test server-side checking of available lessons
    """
    def test_schedule_by_type_no_lesson(self):
        """
        Try to schedule without a lesson
        """
        ordinary_lesson_type = lessons.OrdinaryLesson.contenttype().pk
        response = self._step2(
            view=views.step2_by_type,
            just_checking=True,
            date='2032-05-05',  # wednesday
            time='17:00',
            type_id=ordinary_lesson_type,
        )
        self.assertFalse(response['result'])
        self.assertEquals(response['error'], 'E_CLASS_NOT_FOUND')
        self.assertIn('curated session', response['text'])

        master_class = mixer.blend(lessons.MasterClass, host=self.host)
        entry = mixer.blend(TimelineEntry,
                            teacher=self.host,
                            start=datetime(2032, 5, 3, 14, 0),
                            end=datetime(2032, 5, 3, 14, 30),
                            lesson=master_class
                            )
        response = self._step2(
            view=views.step2_by_entry,
            just_checking=True,
            entry_id=entry.pk,
        )
        self.assertFalse(response['result'])
        self.assertEquals(response['error'], 'E_CLASS_NOT_FOUND')
        self.assertIn('master class', response['text'])

    def test_schedule_by_type_no_slot(self):
        """
        Try to schedule without a teacher slot
        """
        ordinary_lesson_type = lessons.OrdinaryLesson.contenttype().pk
        self._buy_a_lesson(lessons.OrdinaryLesson.get_default())

        response = self._step2(
            view=views.step2_by_type,
            just_checking=True,
            date='2032-05-05',  # wednesday
            time='17:00',
            type_id=ordinary_lesson_type,
        )
        self.assertFalse(response['result'])
        self.assertEquals(response['error'], 'E_CANT_SCHEDULE')

    def test_schedule_an_ordinary_lesson(self):
        """
        Buy an ordinary lesson and try to schedule it via by for the time, when
        teacher is available
        """
        ordinary_lesson_type = lessons.OrdinaryLesson.contenttype().pk
        c = self._buy_a_lesson(lessons.OrdinaryLesson.get_default())
        self.assertFalse(c.is_scheduled)

        self._step2(
            view=views.step2_by_type,
            date='2032-05-03',  # monday
            time='14:00',
            type_id=ordinary_lesson_type,
        )
        c = Class.objects.get(pk=c.pk)
        self.assertTrue(c.is_scheduled)

    def test_schedule_a_master_class(self):
        """
        Buy a master class, create a timeline entry for it and schedule it
        """
        master_class = mixer.blend(lessons.MasterClass, host=self.host)
        entry = mixer.blend(TimelineEntry,
                            teacher=self.host,
                            start=datetime(2032, 5, 3, 14, 0),
                            end=datetime(2032, 5, 3, 14, 30),
                            lesson=master_class
                            )
        c = self._buy_a_lesson(master_class)

        self._step2(
            view=views.step2_by_entry,
            entry_id=entry.pk,
        )

        c = Class.objects.get(pk=c.pk)
        self.assertTrue(c.is_scheduled)