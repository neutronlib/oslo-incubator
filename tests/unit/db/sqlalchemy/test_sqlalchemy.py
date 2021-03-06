# encoding=UTF8

# Copyright (c) 2012 Rackspace Hosting
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

"""Unit tests for SQLAlchemy specific code."""

import _mysql_exceptions
import mock
import sqlalchemy
from sqlalchemy import Column, MetaData, Table, UniqueConstraint
from sqlalchemy import DateTime, Integer, String
from sqlalchemy.exc import DataError
from sqlalchemy.ext.declarative import declarative_base

from openstack.common.db import exception as db_exc
from openstack.common.db.sqlalchemy import models
from openstack.common.db.sqlalchemy import session
from openstack.common.fixture import config
from openstack.common import test
from tests.unit.db.sqlalchemy import base as test_base


BASE = declarative_base()
_TABLE_NAME = '__tmp__test__tmp__'


class TmpTable(BASE, models.ModelBase):
    __tablename__ = _TABLE_NAME
    id = Column(Integer, primary_key=True)
    foo = Column(Integer)


class SessionParametersTestCase(test_base.DbTestCase):

    def setUp(self):
        super(SessionParametersTestCase, self).setUp()
        config_fixture = self.useFixture(config.Config())
        self.conf = config_fixture.conf

    def test_deprecated_session_parameters(self):
        path = self.create_tempfiles([["tmp", """[DEFAULT]
sql_connection=x://y.z
sql_min_pool_size=10
sql_max_pool_size=20
sql_max_retries=30
sql_retry_interval=40
sql_max_overflow=50
sql_connection_debug=60
sql_connection_trace=True
"""]])[0]
        self.conf(['--config-file', path])
        self.assertEqual(self.conf.database.connection, 'x://y.z')
        self.assertEqual(self.conf.database.min_pool_size, 10)
        self.assertEqual(self.conf.database.max_pool_size, 20)
        self.assertEqual(self.conf.database.max_retries, 30)
        self.assertEqual(self.conf.database.retry_interval, 40)
        self.assertEqual(self.conf.database.max_overflow, 50)
        self.assertEqual(self.conf.database.connection_debug, 60)
        self.assertEqual(self.conf.database.connection_trace, True)

    def test_session_parameters(self):
        path = self.create_tempfiles([["tmp", """[database]
connection=x://y.z
min_pool_size=10
max_pool_size=20
max_retries=30
retry_interval=40
max_overflow=50
connection_debug=60
connection_trace=True
pool_timeout=7
"""]])[0]
        self.conf(['--config-file', path])
        self.assertEqual(self.conf.database.connection, 'x://y.z')
        self.assertEqual(self.conf.database.min_pool_size, 10)
        self.assertEqual(self.conf.database.max_pool_size, 20)
        self.assertEqual(self.conf.database.max_retries, 30)
        self.assertEqual(self.conf.database.retry_interval, 40)
        self.assertEqual(self.conf.database.max_overflow, 50)
        self.assertEqual(self.conf.database.connection_debug, 60)
        self.assertEqual(self.conf.database.connection_trace, True)
        self.assertEqual(self.conf.database.pool_timeout, 7)

    def test_dbapi_database_deprecated_parameters(self):
        path = self.create_tempfiles([['tmp', '[DATABASE]\n'
                                      'sql_connection=fake_connection\n'
                                      'sql_idle_timeout=100\n'
                                      'sql_min_pool_size=99\n'
                                      'sql_max_pool_size=199\n'
                                      'sql_max_retries=22\n'
                                      'reconnect_interval=17\n'
                                      'sqlalchemy_max_overflow=101\n'
                                      'sqlalchemy_pool_timeout=5\n'
                                       ]])[0]
        self.conf(['--config-file', path])
        self.assertEqual(self.conf.database.connection, 'fake_connection')
        self.assertEqual(self.conf.database.idle_timeout, 100)
        self.assertEqual(self.conf.database.min_pool_size, 99)
        self.assertEqual(self.conf.database.max_pool_size, 199)
        self.assertEqual(self.conf.database.max_retries, 22)
        self.assertEqual(self.conf.database.retry_interval, 17)
        self.assertEqual(self.conf.database.max_overflow, 101)
        self.assertEqual(self.conf.database.pool_timeout, 5)

    def test_dbapi_database_deprecated_parameters_sql(self):
        path = self.create_tempfiles([['tmp', '[sql]\n'
                                      'connection=test_sql_connection\n'
                                      'idle_timeout=99\n'
                                       ]])[0]
        self.conf(['--config-file', path])
        self.assertEqual(self.conf.database.connection, 'test_sql_connection')
        self.assertEqual(self.conf.database.idle_timeout, 99)


class SessionErrorWrapperTestCase(test_base.DbTestCase):
    def setUp(self):
        super(SessionErrorWrapperTestCase, self).setUp()
        meta = MetaData()
        meta.bind = session.get_engine()
        test_table = Table(_TABLE_NAME, meta,
                           Column('id', Integer, primary_key=True,
                                  nullable=False),
                           Column('deleted', Integer, default=0),
                           Column('deleted_at', DateTime),
                           Column('updated_at', DateTime),
                           Column('created_at', DateTime),
                           Column('foo', Integer),
                           UniqueConstraint('foo', name='uniq_foo'))
        test_table.create()
        self.addCleanup(test_table.drop)

    def test_flush_wrapper(self):
        tbl = TmpTable()
        tbl.update({'foo': 10})
        tbl.save()

        tbl2 = TmpTable()
        tbl2.update({'foo': 10})
        self.assertRaises(db_exc.DBDuplicateEntry, tbl2.save)

    def test_execute_wrapper(self):
        _session = session.get_session()
        with _session.begin():
            for i in [10, 20]:
                tbl = TmpTable()
                tbl.update({'foo': i})
                tbl.save(session=_session)

            method = _session.query(TmpTable).\
                filter_by(foo=10).\
                update
            self.assertRaises(db_exc.DBDuplicateEntry,
                              method, {'foo': 20})


_REGEXP_TABLE_NAME = _TABLE_NAME + "regexp"


class RegexpTable(BASE, models.ModelBase):
    __tablename__ = _REGEXP_TABLE_NAME
    id = Column(Integer, primary_key=True)
    bar = Column(String(255))


class RegexpFilterTestCase(test_base.DbTestCase):

    def setUp(self):
        super(RegexpFilterTestCase, self).setUp()
        meta = MetaData()
        meta.bind = session.get_engine()
        test_table = Table(_REGEXP_TABLE_NAME, meta,
                           Column('id', Integer, primary_key=True,
                                  nullable=False),
                           Column('bar', String(255)))
        test_table.create()
        self.addCleanup(test_table.drop)

    def _test_regexp_filter(self, regexp, expected):
        _session = session.get_session()
        with _session.begin():
            for i in ['10', '20', u'♥']:
                tbl = RegexpTable()
                tbl.update({'bar': i})
                tbl.save(session=_session)

        regexp_op = RegexpTable.bar.op('REGEXP')(regexp)
        result = _session.query(RegexpTable).filter(regexp_op).all()
        self.assertEqual([r.bar for r in result], expected)

    def test_regexp_filter(self):
        self._test_regexp_filter('10', ['10'])

    def test_regexp_filter_nomatch(self):
        self._test_regexp_filter('11', [])

    def test_regexp_filter_unicode(self):
        self._test_regexp_filter(u'♥', [u'♥'])

    def test_regexp_filter_unicode_nomatch(self):
        self._test_regexp_filter(u'♦', [])


class SlaveBackendTestCase(test.BaseTestCase):

    def test_slave_engine_nomatch(self):
        default = session.CONF.database.connection
        session.CONF.database.slave_connection = default

        e = session.get_engine()
        slave_e = session.get_engine(slave_engine=True)
        self.assertNotEqual(slave_e, e)

    def test_no_slave_engine_match(self):
        slave_e = session.get_engine()
        e = session.get_engine()
        self.assertEqual(slave_e, e)

    def test_slave_backend_nomatch(self):
        session.CONF.database.slave_connection = "mysql:///localhost"
        self.assertRaises(AssertionError, session._assert_matching_drivers)


class FakeDBAPIConnection():
    def cursor(self):
        return FakeCursor()


class FakeCursor():
    def execute(self, sql):
        pass


class FakeConnectionProxy():
    pass


class FakeConnectionRec():
    pass


class OperationalError(Exception):
    pass


class ProgrammingError(Exception):
    pass


class FakeDB2Engine(object):

    class Dialect():

        def is_disconnect(self, e, *args):
            expected_error = ('SQL30081N: DB2 Server connection is no longer '
                              'active')
            return (str(e) == expected_error)

    dialect = Dialect()
    name = 'ibm_db_sa'


class TestDBDisconnected(test.BaseTestCase):

    def _test_ping_listener_disconnected(self, connection):
        engine_args = {
            'pool_recycle': 3600,
            'echo': False,
            'convert_unicode': True}

        engine = sqlalchemy.create_engine(connection, **engine_args)

        self.assertRaises(sqlalchemy.exc.DisconnectionError,
                          session._ping_listener, engine,
                          FakeDBAPIConnection(), FakeConnectionRec(),
                          FakeConnectionProxy())

    def test_mysql_ping_listener_disconnected(self):
        def fake_execute(sql):
            raise _mysql_exceptions.OperationalError(self.mysql_error,
                                                     ('MySQL server has '
                                                      'gone away'))
        with mock.patch.object(FakeCursor, 'execute',
                               side_effect=fake_execute):
            connection = 'mysql://root:password@fakehost/fakedb?charset=utf8'
            for code in [2006, 2013, 2014, 2045, 2055]:
                self.mysql_error = code
                self._test_ping_listener_disconnected(connection)

    def test_db2_ping_listener_disconnected(self):

        def fake_execute(sql):
            raise OperationalError('SQL30081N: DB2 Server '
                                   'connection is no longer active')
        with mock.patch.object(FakeCursor, 'execute',
                               side_effect=fake_execute):
            # TODO(dperaza): Need a fake engine for db2 since ibm_db_sa is not
            # in global requirements. Change this code to use real IBM db2
            # engine as soon as ibm_db_sa is included in global-requirements
            # under openstack/requirements project.
            fake_create_engine = lambda *args, **kargs: FakeDB2Engine()
            with mock.patch.object(sqlalchemy, 'create_engine',
                                   side_effect=fake_create_engine):
                connection = ('ibm_db_sa://db2inst1:openstack@fakehost:50000'
                              '/fakedab')
                self._test_ping_listener_disconnected(connection)


class MySQLTraditionalModeTestCase(test_base.MySQLOpportunisticTestCase):

    def setUp(self):
        super(MySQLTraditionalModeTestCase, self).setUp()

        self.engine = session.get_engine(mysql_traditional_mode=True)
        self.connection = self.engine.connect()

        meta = MetaData()
        meta.bind = self.engine
        self.test_table = Table(_TABLE_NAME + "mode", meta,
                                Column('id', Integer, primary_key=True),
                                Column('bar', String(255)))
        self.test_table.create()

        self.addCleanup(session.cleanup)
        self.addCleanup(self.test_table.drop)
        self.addCleanup(self.connection.close)

    def test_string_too_long(self):
        with self.connection.begin():
            self.assertRaises(DataError, self.connection.execute,
                              self.test_table.insert(), bar='a' * 512)
