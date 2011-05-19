import unittest

from mongoengine import *
from mongoengine.connection import _get_db

test_field = 'test_field'
test_value = 'test_value'
    
class FirstDynamicDocumentTest(unittest.TestCase):

    def setUp(self):
        connect(db='mongoenginetest')
        self.db = _get_db()
        class Person(Document):
            name = StringField()
            age = IntField()
        self.Person = Person

    def test_create_dynamic_document(self):
        """Ensure that dynamic documents are successfully stored in database.
        """
        test_person = self.Person(name='Test')
        test_person.create_dynamic_field(test_field, test_value)
        self.assertTrue(test_person._dynamic_fields.has_key(test_field))
        self.assertTrue(test_person._data.has_key(test_field))
        self.assertTrue(test_person._dynamic_fields.has_key('_dynamic_fields_list'))
        self.assertTrue(test_person._data.has_key('_dynamic_fields_list'))
        test_person.save()
        test_person.reload()
        self.assertTrue(test_person._fields.has_key(test_field))
        self.assertTrue(test_person._data.has_key(test_field))
        self.assertTrue(test_person._fields.has_key('_dynamic_fields_list'))
        self.assertTrue(test_person._data.has_key('_dynamic_fields_list'))
        self.assertEqual(test_person.test_field, test_value)
        self.assertEqual(test_person._dynamic_fields_list, ['_dynamic_fields_list', 'test_field'])


class SecondDynamicDocumentTest(unittest.TestCase):

    def setUp(self):
        connect(db='mongoenginetest')
        self.db = _get_db()
        class Person(Document):
            name = StringField()
            age = IntField()
        self.Person = Person

    def test_fetch_dynamic_document(self):
        """Ensure that dynamic documents are successfully read from database.
        """
        collection = self.db[self.Person._meta['collection']]
        test_database_object = collection.find_one({'name': 'Test'})
        self.assertTrue(test_database_object.has_key(test_field))
        self.assertEqual(test_database_object[test_field], test_value)
        self.assertTrue(test_database_object.has_key('_dynamic_fields_list'))
        self.assertEqual(test_database_object['_dynamic_fields_list'], ['_dynamic_fields_list', 'test_field'])
        dynamic_fields_list = test_database_object['_dynamic_fields_list']
        self.assertTrue(test_field in dynamic_fields_list)
        self.assertTrue('_dynamic_fields_list' in dynamic_fields_list)

        test_person = self.Person.objects.get(name='Test')
        self.assertTrue(test_person._fields.has_key(test_field))
        self.assertTrue(test_person._data.has_key(test_field))
        self.assertTrue(test_person._fields.has_key('_dynamic_fields_list'))
        self.assertTrue(test_person._data.has_key('_dynamic_fields_list'))
        self.assertEqual(test_person.test_field, test_value)
        self.assertEqual(test_person._dynamic_fields_list, ['_dynamic_fields_list', 'test_field'])

    def tearDown(self):
        self.Person.drop_collection()

if __name__ == '__main__':
    unittest.main()

