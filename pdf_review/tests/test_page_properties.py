"""Immutable-version metrics reuse, validation, and current ACL/CSRF boundaries."""
import unittest

from review.database import transaction, init_database
from tests import test_reading


class PagePropertiesTests(unittest.TestCase):
    setUp = test_reading.ReadingTests.setUp
    tearDown = test_reading.ReadingTests.tearDown

    def payload(self, words=3):
        return dict(page_count=10, rows=[dict(page=1, words=words, area=100, wordRuns=[[.2, words]])])

    def test_shared_across_readers_not_versions_and_first_success_wins(self):
        url=f'/api/versions/{self.version}/page-properties'
        self.assertEqual(self.http.post(url,json=self.payload()).status_code,200)
        self.assertEqual(self.other.get(url).json['rows'][0]['words'],3)
        self.assertEqual(self.other.post(url,json=self.payload(99)).status_code,200)
        self.assertEqual(self.http.get(url).json['rows'][0]['words'],3)
        self.assertEqual(self.http.get(f'/api/versions/{self.draft4}/page-properties').json['rows'],[])
        init_database(self.database)
        self.assertEqual(self.http.get(url).json['rows'][0]['words'],3)

    def test_blank_valid_unknown_invalid_and_no_partial_batch_write(self):
        url=f'/api/versions/{self.version}/page-properties'
        bad=self.payload();bad['rows'].append(dict(page=2,words=None,area=100,wordRuns=[]))
        self.assertEqual(self.http.post(url,json=bad).status_code,422)
        self.assertEqual(self.http.get(url).json['rows'],[])
        self.assertEqual(self.http.post(url,json=self.payload(0)).status_code,200)
        self.assertEqual(self.http.get(url).json['rows'][0]['words'],0)
        bad=self.payload();bad['rows'][0]['wordRuns']=[[.2,4]]
        self.assertEqual(self.http.post(url,json=bad).status_code,422)

    def test_current_access_viewer_support_and_csrf(self):
        url=f'/api/versions/{self.version}/page-properties'
        with transaction(self.database) as c:
            c.execute("UPDATE document_access SET role='viewer' WHERE user_id=?",(self.beta['user_id'],))
        self.assertEqual(self.other.post(url,json=self.payload()).status_code,200)
        self.assertEqual(self.other.post(url,json=self.payload(),headers={'X-CSRF-Token':'wrong'}).status_code,400)
        with transaction(self.database) as c:
            c.execute('DELETE FROM document_access WHERE user_id=?',(self.beta['user_id'],))
        self.assertEqual(self.other.get(url).status_code,404)
        self.assertEqual(self.other.post(url,json=self.payload()).status_code,404)


if __name__=='__main__':unittest.main()

