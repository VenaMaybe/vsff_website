"""Per-account appearance defaults, validation, and mutation boundaries."""
import unittest
from unittest.mock import patch
from tests import test_accounts
from review.database import init_database, MIGRATIONS, transaction, connect
from review.users import create_user


class AppearanceTests(unittest.TestCase):
    setUp=test_accounts.AccountTests.setUp
    post=test_accounts.AccountTests.post
    sql=test_accounts.AccountTests.sql

    def test_defaults_saved_for_actor_only_and_rendered_before_scripts(self):
        self.assertIn(b'data-ui-theme="light"',self.clients[self.owner].get('/account').data)
        initial=self.clients[self.owner].get(f'/versions/{self.version}/view').data
        self.assertIn(b'data-pdf-color-amount="50" data-pdf-white-point="65"',initial)
        self.assertEqual(self.post(self.reader,'/account/appearance',dict(ui_theme='dark',pdf_theme='dark')).status_code,303)
        self.assertIn(b'data-ui-theme="dark"',self.clients[self.reader].get('/account').data)
        self.assertIn(b'data-ui-theme="light"',self.clients[self.owner].get('/account').data)
        self.assertEqual(self.post(self.owner,'/account/appearance',dict(ui_theme='dark',pdf_theme='light')).status_code,303)
        page=self.clients[self.owner].get(f'/versions/{self.version}/view').data
        self.assertIn(b'data-ui-theme="dark" data-pdf-theme="light"',page)
        self.assertEqual(self.sql('SELECT pdf_color_amount,pdf_white_point FROM account_appearance WHERE user_id=?',(self.owner,)),[dict(pdf_color_amount=50,pdf_white_point=65)])
        init_database(self.db)
        self.assertEqual(self.sql('SELECT ui_theme,pdf_theme FROM account_appearance WHERE user_id=?',(self.owner,)),[dict(ui_theme='dark',pdf_theme='light')])

    def test_invalid_or_forged_settings_do_not_write_and_csrf_required(self):
        url='/account/appearance'
        for values,status in [(dict(ui_theme='bogus',pdf_theme='dark'),422),
                              (dict(ui_theme='dark'),422),
                              (dict(ui_theme='dark',pdf_theme='dark',user_id=self.reader),400)]:
            self.assertEqual(self.post(self.owner,url,values).status_code,status)
        self.assertEqual(self.post(self.owner,url,dict(ui_theme='dark',pdf_theme='dark'),token='wrong').status_code,400)
        self.assertEqual(self.app.test_client().post(url).status_code,401)
        self.assertEqual(self.sql('SELECT * FROM account_appearance'),[])

    def test_reading_color_defaults_validation_and_legacy_saves(self):
        url='/account/appearance'
        values=dict(ui_theme='light',pdf_theme='dark',pdf_monochrome='0',pdf_white_point='70')
        for key,value in [('pdf_monochrome','2'),('pdf_white_point','49'),('pdf_white_point','101'),('pdf_white_point','nan'),('pdf_color_amount','101'),('pdf_color_amount','-1'),('pdf_white_point','9'*10000)]:
            self.assertEqual(self.post(self.owner,url,{**values,key:value}).status_code,422)
        self.assertEqual(self.sql('SELECT * FROM account_appearance'),[])
        self.assertEqual(self.post(self.owner,url,values).status_code,303)
        # Older clients may still send only the original two preferences.
        self.assertEqual(self.post(self.owner,url,dict(ui_theme='dark',pdf_theme='dark')).status_code,303)
        self.assertEqual(self.sql('SELECT pdf_monochrome,pdf_white_point FROM account_appearance WHERE user_id=?',(self.owner,)),[dict(pdf_monochrome=0,pdf_white_point=70)])
        page=self.clients[self.owner].get(f'/versions/{self.version}/view').data
        self.assertIn(b'data-pdf-color-amount="100" data-pdf-white-point="70"',page)
        self.assertEqual(self.post(self.owner,url,{**values,'pdf_color_amount':'25'}).status_code,303)
        self.assertEqual(self.post(self.owner,url,dict(ui_theme='light',pdf_theme='dark')).status_code,303)
        self.assertEqual(self.sql('SELECT pdf_color_amount FROM account_appearance WHERE user_id=?',(self.owner,)),[dict(pdf_color_amount=25)])

    def test_upgrade_preserves_existing_themes_and_adds_neutral_defaults(self):
        previous=self.root/'appearance17.sqlite3'
        with patch('review.database.MIGRATIONS',[m for m in MIGRATIONS if m[0]<=17]):
            init_database(previous)
        user=create_user(previous,'Earlier account')['user_id']
        with transaction(previous) as c:c.execute('INSERT INTO account_appearance VALUES(?,?,?)',(user,'dark','dark'))
        init_database(previous);init_database(previous)
        c=connect(previous)
        try:self.assertEqual(dict(c.execute('SELECT * FROM account_appearance').fetchone()),dict(user_id=user,ui_theme='dark',pdf_theme='dark',pdf_monochrome=1,pdf_white_point=90,pdf_color_amount=0))
        finally:c.close()

    def test_color_slider_upgrade_preserves_prior_color_choice(self):
        previous=self.root/'appearance18.sqlite3'
        with patch('review.database.MIGRATIONS',[m for m in MIGRATIONS if m[0]<=18]):
            init_database(previous)
        user=create_user(previous,'Earlier color account')['user_id']
        with transaction(previous) as c:c.execute('INSERT INTO account_appearance VALUES(?,?,?,?,?)',(user,'light','dark',0,65))
        init_database(previous)
        c=connect(previous)
        try:self.assertEqual(dict(c.execute('SELECT pdf_color_amount,pdf_white_point FROM account_appearance').fetchone()),dict(pdf_color_amount=100,pdf_white_point=65))
        finally:c.close()


if __name__=='__main__':unittest.main()
