import unittest
from datetime import datetime
import pymongo
import pickle
import weakref

from mongoengine import *
from mongoengine.base import BaseField
from mongoengine.connection import _get_db


class PickleEmbedded(EmbeddedDocument):
    date = DateTimeField(default=datetime.now)


class PickleTest(Document):
    number = IntField()
    string = StringField()
    embedded = EmbeddedDocumentField(PickleEmbedded)
    lists = ListField(StringField())


class DocumentTest(unittest.TestCase):

    def setUp(self):
        connect(db='mongoenginetest')
        self.db = _get_db()

        class Person(Document):
            name = StringField()
            age = IntField()
        self.Person = Person

    def tearDown(self):
        self.Person.drop_collection()

    def test_drop_collection(self):
        """Ensure that the collection may be dropped from the database.
        """
        self.Person(name='Test').save()

        collection = self.Person._meta['collection']
        self.assertTrue(collection in self.db.collection_names())

        self.Person.drop_collection()
        self.assertFalse(collection in self.db.collection_names())

    def test_definition(self):
        """Ensure that document may be defined using fields.
        """
        name_field = StringField()
        age_field = IntField()

        class Person(Document):
            name = name_field
            age = age_field
            non_field = True

        self.assertEqual(Person._fields['name'], name_field)
        self.assertEqual(Person._fields['age'], age_field)
        self.assertFalse('non_field' in Person._fields)
        self.assertTrue('id' in Person._fields)
        # Test iteration over fields
        fields = list(Person())
        self.assertTrue('name' in fields and 'age' in fields)
        # Ensure Document isn't treated like an actual document
        self.assertFalse(hasattr(Document, '_fields'))

    def test_get_superclasses(self):
        """Ensure that the correct list of superclasses is assembled.
        """
        class Animal(Document): pass
        class Fish(Animal): pass
        class Mammal(Animal): pass
        class Human(Mammal): pass
        class Dog(Mammal): pass

        mammal_superclasses = {'Animal': Animal}
        self.assertEqual(Mammal._superclasses, mammal_superclasses)

        dog_superclasses = {
            'Animal': Animal,
            'Animal.Mammal': Mammal,
        }
        self.assertEqual(Dog._superclasses, dog_superclasses)

    def test_get_subclasses(self):
        """Ensure that the correct list of subclasses is retrieved by the
        _get_subclasses method.
        """
        class Animal(Document): pass
        class Fish(Animal): pass
        class Mammal(Animal): pass
        class Human(Mammal): pass
        class Dog(Mammal): pass

        mammal_subclasses = {
            'Animal.Mammal.Dog': Dog,
            'Animal.Mammal.Human': Human
        }
        self.assertEqual(Mammal._get_subclasses(), mammal_subclasses)

        animal_subclasses = {
            'Animal.Fish': Fish,
            'Animal.Mammal': Mammal,
            'Animal.Mammal.Dog': Dog,
            'Animal.Mammal.Human': Human
        }
        self.assertEqual(Animal._get_subclasses(), animal_subclasses)

    def test_polymorphic_queries(self):
        """Ensure that the correct subclasses are returned from a query"""
        class Animal(Document): pass
        class Fish(Animal): pass
        class Mammal(Animal): pass
        class Human(Mammal): pass
        class Dog(Mammal): pass

        Animal().save()
        Fish().save()
        Mammal().save()
        Human().save()
        Dog().save()

        classes = [obj.__class__ for obj in Animal.objects]
        self.assertEqual(classes, [Animal, Fish, Mammal, Human, Dog])

        classes = [obj.__class__ for obj in Mammal.objects]
        self.assertEqual(classes, [Mammal, Human, Dog])

        classes = [obj.__class__ for obj in Human.objects]
        self.assertEqual(classes, [Human])

        Animal.drop_collection()

    def test_inheritance(self):
        """Ensure that document may inherit fields from a superclass document.
        """
        class Employee(self.Person):
            salary = IntField()

        self.assertTrue('name' in Employee._fields)
        self.assertTrue('salary' in Employee._fields)
        self.assertEqual(Employee._meta['collection'],
                         self.Person._meta['collection'])

        # Ensure that MRO error is not raised
        class A(Document): pass
        class B(A): pass
        class C(B): pass

    def test_allow_inheritance(self):
        """Ensure that inheritance may be disabled on simple classes and that
        _cls and _types will not be used.
        """

        class Animal(Document):
            name = StringField()
            meta = {'allow_inheritance': False}

        Animal.drop_collection()
        def create_dog_class():
            class Dog(Animal):
                pass
        self.assertRaises(ValueError, create_dog_class)

        # Check that _cls etc aren't present on simple documents
        dog = Animal(name='dog')
        dog.save()
        collection = self.db[Animal._meta['collection']]
        obj = collection.find_one()
        self.assertFalse('_cls' in obj)
        self.assertFalse('_types' in obj)

        Animal.drop_collection()

        def create_employee_class():
            class Employee(self.Person):
                meta = {'allow_inheritance': False}
        self.assertRaises(ValueError, create_employee_class)

        # Test the same for embedded documents
        class Comment(EmbeddedDocument):
            content = StringField()
            meta = {'allow_inheritance': False}

        def create_special_comment():
            class SpecialComment(Comment):
                pass
        self.assertRaises(ValueError, create_special_comment)

        comment = Comment(content='test')
        self.assertFalse('_cls' in comment.to_mongo())
        self.assertFalse('_types' in comment.to_mongo())

    def test_allow_inheritance_abstract_document(self):
        """Ensure that abstract documents can set inheritance rules and that
        _cls and _types will not be used.
        """
        class FinalDocument(Document):
            meta = {'abstract': True,
                    'allow_inheritance': False}

        class Animal(FinalDocument):
            name = StringField()

        Animal.drop_collection()
        def create_dog_class():
            class Dog(Animal):
                pass
        self.assertRaises(ValueError, create_dog_class)

        # Check that _cls etc aren't present on simple documents
        dog = Animal(name='dog')
        dog.save()
        collection = self.db[Animal._meta['collection']]
        obj = collection.find_one()
        self.assertFalse('_cls' in obj)
        self.assertFalse('_types' in obj)

        Animal.drop_collection()

    def test_how_to_turn_off_inheritance(self):
        """Demonstrates migrating from allow_inheritance = True to False.
        """
        class Animal(Document):
            name = StringField()
            meta = {
                'indexes': ['name']
            }

        Animal.drop_collection()

        dog = Animal(name='dog')
        dog.save()

        collection = self.db[Animal._meta['collection']]
        obj = collection.find_one()
        self.assertTrue('_cls' in obj)
        self.assertTrue('_types' in obj)

        info = collection.index_information()
        info = [value['key'] for key, value in info.iteritems()]
        self.assertEquals([[(u'_id', 1)], [(u'_types', 1)], [(u'_types', 1), (u'name', 1)]], info)

        # Turn off inheritance
        class Animal(Document):
            name = StringField()
            meta = {
                'allow_inheritance': False,
                'indexes': ['name']
            }
        collection.update({}, {"$unset": {"_types": 1, "_cls": 1}}, False, True)

        # Confirm extra data is removed
        obj = collection.find_one()
        self.assertFalse('_cls' in obj)
        self.assertFalse('_types' in obj)

        info = collection.index_information()
        info = [value['key'] for key, value in info.iteritems()]
        self.assertEquals([[(u'_id', 1)], [(u'_types', 1)], [(u'_types', 1), (u'name', 1)]], info)

        info = collection.index_information()
        indexes_to_drop = [key for key, value in info.iteritems() if '_types' in dict(value['key'])]
        for index in indexes_to_drop:
            collection.drop_index(index)

        info = collection.index_information()
        info = [value['key'] for key, value in info.iteritems()]
        self.assertEquals([[(u'_id', 1)]], info)

        # Recreate indexes
        dog = Animal.objects.first()
        dog.save()
        info = collection.index_information()
        info = [value['key'] for key, value in info.iteritems()]
        self.assertEquals([[(u'_id', 1)], [(u'name', 1),]], info)

        Animal.drop_collection()

    def test_abstract_documents(self):
        """Ensure that a document superclass can be marked as abstract
        thereby not using it as the name for the collection."""

        class Animal(Document):
            name = StringField()
            meta = {'abstract': True}

        class Fish(Animal): pass
        class Guppy(Fish): pass

        class Mammal(Animal):
            meta = {'abstract': True}
        class Human(Mammal): pass

        self.assertFalse('collection' in Animal._meta)
        self.assertFalse('collection' in Mammal._meta)

        self.assertEqual(Fish._meta['collection'], 'fish')
        self.assertEqual(Guppy._meta['collection'], 'fish')
        self.assertEqual(Human._meta['collection'], 'human')

        def create_bad_abstract():
            class EvilHuman(Human):
                evil = BooleanField(default=True)
                meta = {'abstract': True}
        self.assertRaises(ValueError, create_bad_abstract)

    def test_collection_name(self):
        """Ensure that a collection with a specified name may be used.
        """
        collection = 'personCollTest'
        if collection in self.db.collection_names():
            self.db.drop_collection(collection)

        class Person(Document):
            name = StringField()
            meta = {'collection': collection}

        user = Person(name="Test User")
        user.save()
        self.assertTrue(collection in self.db.collection_names())

        user_obj = self.db[collection].find_one()
        self.assertEqual(user_obj['name'], "Test User")

        user_obj = Person.objects[0]
        self.assertEqual(user_obj.name, "Test User")

        Person.drop_collection()
        self.assertFalse(collection in self.db.collection_names())

    def test_collection_name_and_primary(self):
        """Ensure that a collection with a specified name may be used.
        """

        class Person(Document):
            name = StringField(primary_key=True)
            meta = {'collection': 'app'}

        user = Person(name="Test User")
        user.save()

        user_obj = Person.objects[0]
        self.assertEqual(user_obj.name, "Test User")

        Person.drop_collection()

    def test_inherited_collections(self):
        """Ensure that subclassed documents don't override parents' collections.
        """
        class Drink(Document):
            name = StringField()

        class AlcoholicDrink(Drink):
            meta = {'collection': 'booze'}

        class Drinker(Document):
            drink = GenericReferenceField()

        Drink.drop_collection()
        AlcoholicDrink.drop_collection()
        Drinker.drop_collection()

        red_bull = Drink(name='Red Bull')
        red_bull.save()

        programmer = Drinker(drink=red_bull)
        programmer.save()

        beer = AlcoholicDrink(name='Beer')
        beer.save()

        real_person = Drinker(drink=beer)
        real_person.save()

        self.assertEqual(Drinker.objects[0].drink.name, red_bull.name)
        self.assertEqual(Drinker.objects[1].drink.name, beer.name)

    def test_capped_collection(self):
        """Ensure that capped collections work properly.
        """
        class Log(Document):
            date = DateTimeField(default=datetime.now)
            meta = {
                'max_documents': 10,
                'max_size': 90000,
            }

        Log.drop_collection()

        # Ensure that the collection handles up to its maximum
        for i in range(10):
            Log().save()

        self.assertEqual(len(Log.objects), 10)

        # Check that extra documents don't increase the size
        Log().save()
        self.assertEqual(len(Log.objects), 10)

        options = Log.objects._collection.options()
        self.assertEqual(options['capped'], True)
        self.assertEqual(options['max'], 10)
        self.assertEqual(options['size'], 90000)

        # Check that the document cannot be redefined with different options
        def recreate_log_document():
            class Log(Document):
                date = DateTimeField(default=datetime.now)
                meta = {
                    'max_documents': 11,
                }
            # Create the collection by accessing Document.objects
            Log.objects
        self.assertRaises(InvalidCollectionError, recreate_log_document)

        Log.drop_collection()

    def test_indexes(self):
        """Ensure that indexes are used when meta[indexes] is specified.
        """
        class BlogPost(Document):
            date = DateTimeField(db_field='addDate', default=datetime.now)
            category = StringField()
            tags = ListField(StringField())
            meta = {
                'indexes': [
                    '-date',
                    'tags',
                    ('category', '-date')
                ],
            }

        BlogPost.drop_collection()

        info = BlogPost.objects._collection.index_information()
        # _id, types, '-date', 'tags', ('cat', 'date')
        self.assertEqual(len(info), 5)

        # Indexes are lazy so use list() to perform query
        list(BlogPost.objects)
        info = BlogPost.objects._collection.index_information()
        info = [value['key'] for key, value in info.iteritems()]
        self.assertTrue([('_types', 1), ('category', 1), ('addDate', -1)]
                        in info)
        self.assertTrue([('_types', 1), ('addDate', -1)] in info)
        # tags is a list field so it shouldn't have _types in the index
        self.assertTrue([('tags', 1)] in info)

        class ExtendedBlogPost(BlogPost):
            title = StringField()
            meta = {'indexes': ['title']}

        BlogPost.drop_collection()

        list(ExtendedBlogPost.objects)
        info = ExtendedBlogPost.objects._collection.index_information()
        info = [value['key'] for key, value in info.iteritems()]
        self.assertTrue([('_types', 1), ('category', 1), ('addDate', -1)]
                        in info)
        self.assertTrue([('_types', 1), ('addDate', -1)] in info)
        self.assertTrue([('_types', 1), ('title', 1)] in info)

        BlogPost.drop_collection()


    def test_dictionary_indexes(self):
        """Ensure that indexes are used when meta[indexes] contains dictionaries
        instead of lists.
        """
        class BlogPost(Document):
            date = DateTimeField(db_field='addDate', default=datetime.now)
            category = StringField()
            tags = ListField(StringField())
            meta = {
                'indexes': [
                    { 'fields': ['-date'], 'unique': True,
                      'sparse': True, 'types': False },
                ],
            }

        BlogPost.drop_collection()

        info = BlogPost.objects._collection.index_information()
        # _id, '-date'
        self.assertEqual(len(info), 3)

        # Indexes are lazy so use list() to perform query
        list(BlogPost.objects)
        info = BlogPost.objects._collection.index_information()
        info = [(value['key'],
                 value.get('unique', False),
                 value.get('sparse', False))
                for key, value in info.iteritems()]
        self.assertTrue(([('addDate', -1)], True, True) in info)

        BlogPost.drop_collection()


    def test_unique(self):
        """Ensure that uniqueness constraints are applied to fields.
        """
        class BlogPost(Document):
            title = StringField()
            slug = StringField(unique=True)

        BlogPost.drop_collection()

        post1 = BlogPost(title='test1', slug='test')
        post1.save()

        # Two posts with the same slug is not allowed
        post2 = BlogPost(title='test2', slug='test')
        self.assertRaises(OperationError, post2.save)


    def test_unique_with(self):
        """Ensure that unique_with constraints are applied to fields.
        """
        class Date(EmbeddedDocument):
            year = IntField(db_field='yr')

        class BlogPost(Document):
            title = StringField()
            date = EmbeddedDocumentField(Date)
            slug = StringField(unique_with='date.year')

        BlogPost.drop_collection()

        post1 = BlogPost(title='test1', date=Date(year=2009), slug='test')
        post1.save()

        # day is different so won't raise exception
        post2 = BlogPost(title='test2', date=Date(year=2010), slug='test')
        post2.save()

        # Now there will be two docs with the same slug and the same day: fail
        post3 = BlogPost(title='test3', date=Date(year=2010), slug='test')
        self.assertRaises(OperationError, post3.save)

        BlogPost.drop_collection()

    def test_unique_embedded_document(self):
        """Ensure that uniqueness constraints are applied to fields on embedded documents.
        """
        class SubDocument(EmbeddedDocument):
            year = IntField(db_field='yr')
            slug = StringField(unique=True)

        class BlogPost(Document):
            title = StringField()
            sub = EmbeddedDocumentField(SubDocument)

        BlogPost.drop_collection()

        post1 = BlogPost(title='test1', sub=SubDocument(year=2009, slug="test"))
        post1.save()

        # sub.slug is different so won't raise exception
        post2 = BlogPost(title='test2', sub=SubDocument(year=2010, slug='another-slug'))
        post2.save()

        # Now there will be two docs with the same sub.slug
        post3 = BlogPost(title='test3', sub=SubDocument(year=2010, slug='test'))
        self.assertRaises(OperationError, post3.save)

        BlogPost.drop_collection()

    def test_unique_with_embedded_document_and_embedded_unique(self):
        """Ensure that uniqueness constraints are applied to fields on
        embedded documents.  And work with unique_with as well.
        """
        class SubDocument(EmbeddedDocument):
            year = IntField(db_field='yr')
            slug = StringField(unique=True)

        class BlogPost(Document):
            title = StringField(unique_with='sub.year')
            sub = EmbeddedDocumentField(SubDocument)

        BlogPost.drop_collection()

        post1 = BlogPost(title='test1', sub=SubDocument(year=2009, slug="test"))
        post1.save()

        # sub.slug is different so won't raise exception
        post2 = BlogPost(title='test2', sub=SubDocument(year=2010, slug='another-slug'))
        post2.save()

        # Now there will be two docs with the same sub.slug
        post3 = BlogPost(title='test3', sub=SubDocument(year=2010, slug='test'))
        self.assertRaises(OperationError, post3.save)

        # Now there will be two docs with the same title and year
        post3 = BlogPost(title='test1', sub=SubDocument(year=2009, slug='test-1'))
        self.assertRaises(OperationError, post3.save)

        BlogPost.drop_collection()

    def test_unique_and_indexes(self):
        """Ensure that 'unique' constraints aren't overridden by
        meta.indexes.
        """
        class Customer(Document):
            cust_id = IntField(unique=True, required=True)
            meta = {
                'indexes': ['cust_id'],
                'allow_inheritance': False,
            }

        Customer.drop_collection()
        cust = Customer(cust_id=1)
        cust.save()

        cust_dupe = Customer(cust_id=1)
        try:
            cust_dupe.save()
            raise AssertionError, "We saved a dupe!"
        except OperationError:
            pass
        Customer.drop_collection()

    def test_unique_and_primary(self):
        """If you set a field as primary, then unexpected behaviour can occur.
        You won't create a duplicate but you will update an existing document.
        """

        class User(Document):
            name = StringField(primary_key=True, unique=True)
            password = StringField()

        User.drop_collection()

        user = User(name='huangz', password='secret')
        user.save()

        user = User(name='huangz', password='secret2')
        user.save()

        self.assertEqual(User.objects.count(), 1)
        self.assertEqual(User.objects.get().password, 'secret2')

        User.drop_collection()

    def test_custom_id_field(self):
        """Ensure that documents may be created with custom primary keys.
        """
        class User(Document):
            username = StringField(primary_key=True)
            name = StringField()

        User.drop_collection()

        self.assertEqual(User._fields['username'].db_field, '_id')
        self.assertEqual(User._meta['id_field'], 'username')

        def create_invalid_user():
            User(name='test').save() # no primary key field
        self.assertRaises(ValidationError, create_invalid_user)

        def define_invalid_user():
            class EmailUser(User):
                email = StringField(primary_key=True)
        self.assertRaises(ValueError, define_invalid_user)

        class EmailUser(User):
            email = StringField()

        user = User(username='test', name='test user')
        user.save()

        user_obj = User.objects.first()
        self.assertEqual(user_obj.id, 'test')
        self.assertEqual(user_obj.pk, 'test')

        user_son = User.objects._collection.find_one()
        self.assertEqual(user_son['_id'], 'test')
        self.assertTrue('username' not in user_son['_id'])

        User.drop_collection()

        user = User(pk='mongo', name='mongo user')
        user.save()

        user_obj = User.objects.first()
        self.assertEqual(user_obj.id, 'mongo')
        self.assertEqual(user_obj.pk, 'mongo')

        user_son = User.objects._collection.find_one()
        self.assertEqual(user_son['_id'], 'mongo')
        self.assertTrue('username' not in user_son['_id'])

        User.drop_collection()

    def test_creation(self):
        """Ensure that document may be created using keyword arguments.
        """
        person = self.Person(name="Test User", age=30)
        self.assertEqual(person.name, "Test User")
        self.assertEqual(person.age, 30)

    def test_reload(self):
        """Ensure that attributes may be reloaded.
        """
        person = self.Person(name="Test User", age=20)
        person.save()

        person_obj = self.Person.objects.first()
        person_obj.name = "Mr Test User"
        person_obj.age = 21
        person_obj.save()

        self.assertEqual(person.name, "Test User")
        self.assertEqual(person.age, 20)

        person.reload()
        self.assertEqual(person.name, "Mr Test User")
        self.assertEqual(person.age, 21)

    def test_reload_referencing(self):
        """Ensures reloading updates weakrefs correctly
        """
        class Embedded(EmbeddedDocument):
            dict_field = DictField()
            list_field = ListField()

        class Doc(Document):
            dict_field = DictField()
            list_field = ListField()
            embedded_field = EmbeddedDocumentField(Embedded)

        Doc.drop_collection
        doc = Doc()
        doc.dict_field = {'hello': 'world'}
        doc.list_field = ['1', 2, {'hello': 'world'}]

        embedded_1 = Embedded()
        embedded_1.dict_field = {'hello': 'world'}
        embedded_1.list_field = ['1', 2, {'hello': 'world'}]
        doc.embedded_field = embedded_1
        doc.save()

        doc.reload()
        doc.list_field.append(1)
        doc.dict_field['woot'] = "woot"
        doc.embedded_field.list_field.append(1)
        doc.embedded_field.dict_field['woot'] = "woot"

        self.assertEquals(doc._get_changed_fields(), [
            'list_field', 'dict_field', 'embedded_field.list_field',
            'embedded_field.dict_field'])
        doc.save()

        doc.reload()
        self.assertEquals(doc._get_changed_fields(), [])
        self.assertEquals(len(doc.list_field), 4)
        self.assertEquals(len(doc.dict_field), 2)
        self.assertEquals(len(doc.embedded_field.list_field), 4)
        self.assertEquals(len(doc.embedded_field.dict_field), 2)

    def test_dictionary_access(self):
        """Ensure that dictionary-style field access works properly.
        """
        person = self.Person(name='Test User', age=30)
        self.assertEquals(person['name'], 'Test User')

        self.assertRaises(KeyError, person.__getitem__, 'salary')
        self.assertRaises(KeyError, person.__setitem__, 'salary', 50)

        person['name'] = 'Another User'
        self.assertEquals(person['name'], 'Another User')

        # Length = length(assigned fields + id)
        self.assertEquals(len(person), 3)

        self.assertTrue('age' in person)
        person.age = None
        self.assertFalse('age' in person)
        self.assertFalse('nationality' in person)

    def test_embedded_document(self):
        """Ensure that embedded documents are set up correctly.
        """
        class Comment(EmbeddedDocument):
            content = StringField()

        self.assertTrue('content' in Comment._fields)
        self.assertFalse('id' in Comment._fields)
        self.assertFalse('collection' in Comment._meta)

    def test_embedded_document_validation(self):
        """Ensure that embedded documents may be validated.
        """
        class Comment(EmbeddedDocument):
            date = DateTimeField()
            content = StringField(required=True)

        comment = Comment()
        self.assertRaises(ValidationError, comment.validate)

        comment.content = 'test'
        comment.validate()

        comment.date = 4
        self.assertRaises(ValidationError, comment.validate)

        comment.date = datetime.now()
        comment.validate()

    def test_save(self):
        """Ensure that a document may be saved in the database.
        """
        # Create person object and save it to the database
        person = self.Person(name='Test User', age=30)
        person.save()
        # Ensure that the object is in the database
        collection = self.db[self.Person._meta['collection']]
        person_obj = collection.find_one({'name': 'Test User'})
        self.assertEqual(person_obj['name'], 'Test User')
        self.assertEqual(person_obj['age'], 30)
        self.assertEqual(person_obj['_id'], person.id)
        # Test skipping validation on save
        class Recipient(Document):
            email = EmailField(required=True)

        recipient = Recipient(email='root@localhost')
        self.assertRaises(ValidationError, recipient.save)
        try:
            recipient.save(validate=False)
        except ValidationError:
            self.fail()

    def test_update(self):
        """Ensure that an existing document is updated instead of be overwritten.
        """
        # Create person object and save it to the database
        person = self.Person(name='Test User', age=30)
        person.save()

        # Create same person object, with same id, without age
        same_person = self.Person(name='Test')
        same_person.id = person.id
        same_person.save()

        # Confirm only one object
        self.assertEquals(self.Person.objects.count(), 1)

        # reload
        person.reload()
        same_person.reload()

        # Confirm the same
        self.assertEqual(person, same_person)
        self.assertEqual(person.name, same_person.name)
        self.assertEqual(person.age, same_person.age)

        # Confirm the saved values
        self.assertEqual(person.name, 'Test')
        self.assertEqual(person.age, 30)

        # Test only / exclude only updates included fields
        person = self.Person.objects.only('name').get()
        person.name = 'User'
        person.save()

        person.reload()
        self.assertEqual(person.name, 'User')
        self.assertEqual(person.age, 30)

        # test exclude only updates set fields
        person = self.Person.objects.exclude('name').get()
        person.age = 21
        person.save()

        person.reload()
        self.assertEqual(person.name, 'User')
        self.assertEqual(person.age, 21)

        # Test only / exclude can set non excluded / included fields
        person = self.Person.objects.only('name').get()
        person.name = 'Test'
        person.age = 30
        person.save()

        person.reload()
        self.assertEqual(person.name, 'Test')
        self.assertEqual(person.age, 30)

        # test exclude only updates set fields
        person = self.Person.objects.exclude('name').get()
        person.name = 'User'
        person.age = 21
        person.save()

        person.reload()
        self.assertEqual(person.name, 'User')
        self.assertEqual(person.age, 21)

        # Confirm does remove unrequired fields
        person = self.Person.objects.exclude('name').get()
        person.age = None
        person.save()

        person.reload()
        self.assertEqual(person.name, 'User')
        self.assertEqual(person.age, None)

        person = self.Person.objects.get()
        person.name = None
        person.age = None
        person.save()

        person.reload()
        self.assertEqual(person.name, None)
        self.assertEqual(person.age, None)

    def test_delta(self):

        class Doc(Document):
            string_field = StringField()
            int_field = IntField()
            dict_field = DictField()
            list_field = ListField()

        Doc.drop_collection
        doc = Doc()
        doc.save()

        doc = Doc.objects.first()
        self.assertEquals(doc._get_changed_fields(), [])
        self.assertEquals(doc._delta(), ({}, {}))

        doc.string_field = 'hello'
        self.assertEquals(doc._delta(), ({'string_field': 'hello'}, {}))

        doc._changed_fields = []
        doc.int_field = 1
        self.assertEquals(doc._delta(), ({'int_field': 1}, {}))

        doc._changed_fields = []
        dict_value = {'hello': 'world', 'ping': 'pong'}
        doc.dict_field = dict_value
        self.assertEquals(doc._delta(), ({'dict_field': dict_value}, {}))

        doc._changed_fields = []
        list_value = ['1', 2, {'hello': 'world'}]
        doc.list_field = list_value
        self.assertEquals(doc._delta(), ({'list_field': list_value}, {}))

        # Test unsetting
        doc._changed_fields = []
        doc._unset_fields = []
        doc.dict_field = {}
        self.assertEquals(doc._delta(), ({}, {'dict_field': 1}))

        doc._changed_fields = []
        doc._unset_fields = {}
        doc.list_field = []
        self.assertEquals(doc._delta(), ({}, {'list_field': 1}))

    def test_delta_recursive(self):

        class Embedded(EmbeddedDocument):
            string_field = StringField()
            int_field = IntField()
            dict_field = DictField()
            list_field = ListField()

        class Doc(Document):
            string_field = StringField()
            int_field = IntField()
            dict_field = DictField()
            list_field = ListField()
            embedded_field = EmbeddedDocumentField(Embedded)

        Doc.drop_collection
        doc = Doc()
        doc.save()

        doc = Doc.objects.first()
        self.assertEquals(doc._get_changed_fields(), [])
        self.assertEquals(doc._delta(), ({}, {}))

        embedded_1 = Embedded()
        embedded_1.string_field = 'hello'
        embedded_1.int_field = 1
        embedded_1.dict_field = {'hello': 'world'}
        embedded_1.list_field = ['1', 2, {'hello': 'world'}]
        doc.embedded_field = embedded_1

        embedded_delta = {
            '_types': ['Embedded'],
            '_cls': 'Embedded',
            'string_field': 'hello',
            'int_field': 1,
            'dict_field': {'hello': 'world'},
            'list_field': ['1', 2, {'hello': 'world'}]
        }
        self.assertEquals(doc.embedded_field._delta(), (embedded_delta, {}))
        self.assertEquals(doc._delta(), ({'embedded_field': embedded_delta}, {}))

        doc.save()
        doc.reload()

        doc.embedded_field.dict_field = {}
        self.assertEquals(doc.embedded_field._delta(), ({}, {'dict_field': 1}))
        self.assertEquals(doc._delta(), ({}, {'embedded_field.dict_field': 1}))
        doc.save()
        doc.reload()
        self.assertEquals(doc.embedded_field.dict_field, {})

        doc.embedded_field.list_field = []
        self.assertEquals(doc.embedded_field._delta(), ({}, {'list_field': 1}))
        self.assertEquals(doc._delta(), ({}, {'embedded_field.list_field': 1}))
        doc.save()
        doc.reload()
        self.assertEquals(doc.embedded_field.list_field, [])

        embedded_2 = Embedded()
        embedded_2.string_field = 'hello'
        embedded_2.int_field = 1
        embedded_2.dict_field = {'hello': 'world'}
        embedded_2.list_field = ['1', 2, {'hello': 'world'}]

        doc.embedded_field.list_field = ['1', 2, embedded_2]
        self.assertEquals(doc.embedded_field._delta(), ({
            'list_field': ['1', 2, {
                '_cls': 'Embedded',
                '_types': ['Embedded'],
                'string_field': 'hello',
                'dict_field': {'hello': 'world'},
                'int_field': 1,
                'list_field': ['1', 2, {'hello': 'world'}],
            }]
        }, {}))

        self.assertEquals(doc._delta(), ({
            'embedded_field.list_field': ['1', 2, {
                '_cls': 'Embedded',
                 '_types': ['Embedded'],
                 'string_field': 'hello',
                 'dict_field': {'hello': 'world'},
                 'int_field': 1,
                 'list_field': ['1', 2, {'hello': 'world'}],
            }]
        }, {}))
        doc.save()
        doc.reload()

        self.assertEquals(doc.embedded_field.list_field[0], '1')
        self.assertEquals(doc.embedded_field.list_field[1], 2)
        for k in doc.embedded_field.list_field[2]._fields:
            self.assertEquals(doc.embedded_field.list_field[2][k], embedded_2[k])

        doc.embedded_field.list_field[2].string_field = 'world'
        self.assertEquals(doc.embedded_field._delta(), ({'list_field.2.string_field': 'world'}, {}))
        self.assertEquals(doc._delta(), ({'embedded_field.list_field.2.string_field': 'world'}, {}))
        doc.save()
        doc.reload()
        self.assertEquals(doc.embedded_field.list_field[2].string_field, 'world')

        # Test list native methods
        doc.embedded_field.list_field[2].list_field.pop(0)
        self.assertEquals(doc._delta(), ({'embedded_field.list_field.2.list_field': [2, {'hello': 'world'}]}, {}))
        doc.save()
        doc.reload()

        doc.embedded_field.list_field[2].list_field.append(1)
        self.assertEquals(doc._delta(), ({'embedded_field.list_field.2.list_field': [2, {'hello': 'world'}, 1]}, {}))
        doc.save()
        doc.reload()
        self.assertEquals(doc.embedded_field.list_field[2].list_field, [2, {'hello': 'world'}, 1])

        doc.embedded_field.list_field[2].list_field.sort()
        doc.save()
        doc.reload()
        self.assertEquals(doc.embedded_field.list_field[2].list_field, [1, 2, {'hello': 'world'}])

        del(doc.embedded_field.list_field[2].list_field[2]['hello'])
        self.assertEquals(doc._delta(), ({'embedded_field.list_field.2.list_field': [1, 2, {}]}, {}))
        doc.save()
        doc.reload()

        del(doc.embedded_field.list_field[2].list_field)
        self.assertEquals(doc._delta(), ({}, {'embedded_field.list_field.2.list_field': 1}))

    def test_save_only_changed_fields(self):
        """Ensure save only sets / unsets changed fields
        """

        # Create person object and save it to the database
        person = self.Person(name='Test User', age=30)
        person.save()
        person.reload()

        same_person = self.Person.objects.get()

        person.age = 21
        same_person.name = 'User'

        person.save()
        same_person.save()

        person = self.Person.objects.get()
        self.assertEquals(person.name, 'User')
        self.assertEquals(person.age, 21)

    def test_delete(self):
        """Ensure that document may be deleted using the delete method.
        """
        person = self.Person(name="Test User", age=30)
        person.save()
        self.assertEqual(len(self.Person.objects), 1)
        person.delete()
        self.assertEqual(len(self.Person.objects), 0)

    def test_save_custom_id(self):
        """Ensure that a document may be saved with a custom _id.
        """
        # Create person object and save it to the database
        person = self.Person(name='Test User', age=30,
                             id='497ce96f395f2f052a494fd4')
        person.save()
        # Ensure that the object is in the database with the correct _id
        collection = self.db[self.Person._meta['collection']]
        person_obj = collection.find_one({'name': 'Test User'})
        self.assertEqual(str(person_obj['_id']), '497ce96f395f2f052a494fd4')

    def test_save_custom_pk(self):
        """Ensure that a document may be saved with a custom _id using pk alias.
        """
        # Create person object and save it to the database
        person = self.Person(name='Test User', age=30,
                             pk='497ce96f395f2f052a494fd4')
        person.save()
        # Ensure that the object is in the database with the correct _id
        collection = self.db[self.Person._meta['collection']]
        person_obj = collection.find_one({'name': 'Test User'})
        self.assertEqual(str(person_obj['_id']), '497ce96f395f2f052a494fd4')

    def test_save_list(self):
        """Ensure that a list field may be properly saved.
        """
        class Comment(EmbeddedDocument):
            content = StringField()

        class BlogPost(Document):
            content = StringField()
            comments = ListField(EmbeddedDocumentField(Comment))
            tags = ListField(StringField())

        BlogPost.drop_collection()

        post = BlogPost(content='Went for a walk today...')
        post.tags = tags = ['fun', 'leisure']
        comments = [Comment(content='Good for you'), Comment(content='Yay.')]
        post.comments = comments
        post.save()

        collection = self.db[BlogPost._meta['collection']]
        post_obj = collection.find_one()
        self.assertEqual(post_obj['tags'], tags)
        for comment_obj, comment in zip(post_obj['comments'], comments):
            self.assertEqual(comment_obj['content'], comment['content'])

        BlogPost.drop_collection()

    def test_save_embedded_document(self):
        """Ensure that a document with an embedded document field may be
        saved in the database.
        """
        class EmployeeDetails(EmbeddedDocument):
            position = StringField()

        class Employee(self.Person):
            salary = IntField()
            details = EmbeddedDocumentField(EmployeeDetails)

        # Create employee object and save it to the database
        employee = Employee(name='Test Employee', age=50, salary=20000)
        employee.details = EmployeeDetails(position='Developer')
        employee.save()

        # Ensure that the object is in the database
        collection = self.db[self.Person._meta['collection']]
        employee_obj = collection.find_one({'name': 'Test Employee'})
        self.assertEqual(employee_obj['name'], 'Test Employee')
        self.assertEqual(employee_obj['age'], 50)
        # Ensure that the 'details' embedded object saved correctly
        self.assertEqual(employee_obj['details']['position'], 'Developer')

    def test_updating_an_embedded_document(self):
        """Ensure that a document with an embedded document field may be
        saved in the database.
        """
        class EmployeeDetails(EmbeddedDocument):
            position = StringField()

        class Employee(self.Person):
            salary = IntField()
            details = EmbeddedDocumentField(EmployeeDetails)

        # Create employee object and save it to the database
        employee = Employee(name='Test Employee', age=50, salary=20000)
        employee.details = EmployeeDetails(position='Developer')
        employee.save()

        # Test updating an embedded document
        promoted_employee = Employee.objects.get(name='Test Employee')
        promoted_employee.details.position = 'Senior Developer'
        promoted_employee.save()

        promoted_employee.reload()
        self.assertEqual(promoted_employee.name, 'Test Employee')
        self.assertEqual(promoted_employee.age, 50)
        # Ensure that the 'details' embedded object saved correctly
        self.assertEqual(promoted_employee.details.position, 'Senior Developer')

        # Test removal
        promoted_employee.details = None
        promoted_employee.save()

        promoted_employee.reload()
        self.assertEqual(promoted_employee.details, None)


    def test_save_reference(self):
        """Ensure that a document reference field may be saved in the database.
        """

        class BlogPost(Document):
            meta = {'collection': 'blogpost_1'}
            content = StringField()
            author = ReferenceField(self.Person)

        BlogPost.drop_collection()

        author = self.Person(name='Test User')
        author.save()

        post = BlogPost(content='Watched some TV today... how exciting.')
        # Should only reference author when saving
        post.author = author
        post.save()

        post_obj = BlogPost.objects.first()

        # Test laziness
        self.assertTrue(isinstance(post_obj._data['author'],
                                   pymongo.dbref.DBRef))
        self.assertTrue(isinstance(post_obj.author, self.Person))
        self.assertEqual(post_obj.author.name, 'Test User')

        # Ensure that the dereferenced object may be changed and saved
        post_obj.author.age = 25
        post_obj.author.save()

        author = list(self.Person.objects(name='Test User'))[-1]
        self.assertEqual(author.age, 25)

        BlogPost.drop_collection()


    def test_reverse_delete_rule_cascade_and_nullify(self):
        """Ensure that a referenced document is also deleted upon deletion.
        """

        class BlogPost(Document):
            content = StringField()
            author = ReferenceField(self.Person, reverse_delete_rule=CASCADE)
            reviewer = ReferenceField(self.Person, reverse_delete_rule=NULLIFY)

        self.Person.drop_collection()
        BlogPost.drop_collection()

        author = self.Person(name='Test User')
        author.save()

        reviewer = self.Person(name='Re Viewer')
        reviewer.save()

        post = BlogPost(content = 'Watched some TV')
        post.author = author
        post.reviewer = reviewer
        post.save()

        reviewer.delete()
        self.assertEqual(len(BlogPost.objects), 1)  # No effect on the BlogPost
        self.assertEqual(BlogPost.objects.get().reviewer, None)

        # Delete the Person, which should lead to deletion of the BlogPost, too
        author.delete()
        self.assertEqual(len(BlogPost.objects), 0)

    def test_reverse_delete_rule_cascade_recurs(self):
        """Ensure that a chain of documents is also deleted upon cascaded
        deletion.
        """

        class BlogPost(Document):
            content = StringField()
            author = ReferenceField(self.Person, reverse_delete_rule=CASCADE)

        class Comment(Document):
            text = StringField()
            post = ReferenceField(BlogPost, reverse_delete_rule=CASCADE)


        author = self.Person(name='Test User')
        author.save()

        post = BlogPost(content = 'Watched some TV')
        post.author = author
        post.save()

        comment = Comment(text = 'Kudos.')
        comment.post = post
        comment.save()

        # Delete the Person, which should lead to deletion of the BlogPost, and,
        # recursively to the Comment, too
        author.delete()
        self.assertEqual(len(Comment.objects), 0)

        self.Person.drop_collection()
        BlogPost.drop_collection()
        Comment.drop_collection()

    def test_reverse_delete_rule_deny(self):
        """Ensure that a document cannot be referenced if there are still
        documents referring to it.
        """

        class BlogPost(Document):
            content = StringField()
            author = ReferenceField(self.Person, reverse_delete_rule=DENY)

        self.Person.drop_collection()
        BlogPost.drop_collection()

        author = self.Person(name='Test User')
        author.save()

        post = BlogPost(content = 'Watched some TV')
        post.author = author
        post.save()

        # Delete the Person should be denied
        self.assertRaises(OperationError, author.delete)  # Should raise denied error
        self.assertEqual(len(BlogPost.objects), 1)  # No objects may have been deleted
        self.assertEqual(len(self.Person.objects), 1)

        # Other users, that don't have BlogPosts must be removable, like normal
        author = self.Person(name='Another User')
        author.save()

        self.assertEqual(len(self.Person.objects), 2)
        author.delete()
        self.assertEqual(len(self.Person.objects), 1)

        self.Person.drop_collection()
        BlogPost.drop_collection()

    def subclasses_and_unique_keys_works(self):

        class A(Document):
            pass

        class B(A):
            foo = BooleanField(unique=True)

        A.drop_collection()
        B.drop_collection()

        A().save()
        A().save()
        B(foo=True).save()

        self.assertEquals(A.objects.count(), 2)
        self.assertEquals(B.objects.count(), 1)
        A.drop_collection()
        B.drop_collection()

    def test_document_hash(self):
        """Test document in list, dict, set
        """
        class User(Document):
            pass

        class BlogPost(Document):
            pass

        # Clear old datas
        User.drop_collection()
        BlogPost.drop_collection()

        u1 = User.objects.create()
        u2 = User.objects.create()
        u3 = User.objects.create()
        u4 = User() # New object

        b1 = BlogPost.objects.create()
        b2 = BlogPost.objects.create()

        # in List
        all_user_list = list(User.objects.all())

        self.assertTrue(u1 in all_user_list)
        self.assertTrue(u2 in all_user_list)
        self.assertTrue(u3 in all_user_list)
        self.assertFalse(u4 in all_user_list) # New object
        self.assertFalse(b1 in all_user_list) # Other object
        self.assertFalse(b2 in all_user_list) # Other object

        # in Dict
        all_user_dic = {}
        for u in User.objects.all():
            all_user_dic[u] = "OK"

        self.assertEqual(all_user_dic.get(u1, False), "OK" )
        self.assertEqual(all_user_dic.get(u2, False), "OK" )
        self.assertEqual(all_user_dic.get(u3, False), "OK" )
        self.assertEqual(all_user_dic.get(u4, False), False ) # New object
        self.assertEqual(all_user_dic.get(b1, False), False ) # Other object
        self.assertEqual(all_user_dic.get(b2, False), False ) # Other object

        # in Set
        all_user_set = set(User.objects.all())

        self.assertTrue(u1 in all_user_set )

    def test_picklable(self):

        pickle_doc = PickleTest(number=1, string="OH HAI", lists=['1', '2'])
        pickle_doc.embedded = PickleEmbedded()
        pickle_doc.save()

        pickled_doc = pickle.dumps(pickle_doc)
        resurrected = pickle.loads(pickled_doc)

        self.assertEquals(resurrected, pickle_doc)

        resurrected.string = "Working"
        resurrected.save()

        pickle_doc.reload()
        self.assertEquals(resurrected, pickle_doc)

    def test_write_options(self):
        """Test that passing write_options works"""

        self.Person.drop_collection()

        write_options = {"fsync": True}

        author, created = self.Person.objects.get_or_create(
                            name='Test User', write_options=write_options)
        author.save(write_options=write_options)

        self.Person.objects.update(set__name='Ross', write_options=write_options)

        author = self.Person.objects.first()
        self.assertEquals(author.name, 'Ross')

        self.Person.objects.update_one(set__name='Test User', write_options=write_options)
        author = self.Person.objects.first()
        self.assertEquals(author.name, 'Test User')


if __name__ == '__main__':
    unittest.main()
