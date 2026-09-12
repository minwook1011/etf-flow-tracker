import unittest
from publish_pages import decision


class PublicationTests(unittest.TestCase):
    def test_no_change_still_recovers_failed_publication(self):
        self.assertEqual(decision({"status":"built","commit":"old"},"new"),"request")
        self.assertEqual(decision({"status":"errored","commit":"new"},"new"),"request")

    def test_coalesce_and_skip_already_published(self):
        self.assertEqual(decision({"status":"queued","commit":"old"},"new"),"in_progress")
        self.assertEqual(decision({"status":"built","commit":"new"},"new"),"current")
        self.assertEqual(decision(None,"new"),"request")
