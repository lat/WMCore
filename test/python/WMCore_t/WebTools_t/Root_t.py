#!/usr/bin/env python

import unittest
import logging
import urllib2
from WMCore.WebTools.Root import Root
from WMCore.Configuration import Configuration
from cherrypy import engine, tree
from cherrypy import config as cpconfig
from tempfile import NamedTemporaryFile

class RootTest(unittest.TestCase):

    def getBaseConfiguration(self):
        config = Configuration()
        config.component_('SecurityModule')
        config.SecurityModule.dangerously_insecure = True

        config.component_('Webtools')
        config.Webtools.application = 'UnitTests'
        config.Webtools.log_screen = False
        config.Webtools.environment = "development"
        config.Webtools.error_log_level = logging.WARNING
        config.Webtools.access_log_level = logging.DEBUG
        config.Webtools.host = "127.0.0.1"
        config.component_('UnitTests')
        config.UnitTests.admin = "Mr Unit Test"
        config.UnitTests.description = "Dummy server for unit tests"
        config.UnitTests.title = "Unit Tests"
        config.UnitTests.section_('views')
        active = config.UnitTests.views.section_('active')

        return config

    def testLongHandConfigurables(self):
        """
        Test that the following configuration variables work:

        engine 	    Controls the "application engine", including autoreload.
                    These can only be declared in the global config.
        hooks 	    Declares additional request-processing functions.
        log 	    Configures the logging for each application. These can only
                    be declared in the global or / config.
        request 	Adds attributes to each Request.
        response 	Adds attributes to each Response.
        server 	    Controls the default HTTP server via cherrypy.server. These
                    can only be declared in the global config.
        tools 	    Runs and configures additional request-processing packages.
        wsgi 	    Adds WSGI middleware to an Application's "pipeline". These
                    can only be declared in the app's root config ("/").
        checker 	Controls the "checker", which looks for common errors in app
                    state (including config) when the engine starts. Global config only.

        (from http://docs.cherrypy.org/dev/intro/concepts/config.html)
        """
        config = self.getBaseConfiguration()

        server = Root(config)
        server.start(blocking=False)
        server.stop()

    def testFakeLongHandConfigurables(self):
        """
        Test that a made up long hand configurable is ignored
        """
        config = self.getBaseConfiguration()
        # The following should be ignored by the configure step
        config.Webtools.section_('foo')
        config.Webtools.foo.bar = 'baz'
        config.Webtools.section_('stuff')
        config.Webtools.stuff = 'things'

        server = Root(config)
        server.start(blocking=False)

        self.assertFalse('foo' in cpconfig.keys(), 'non-standard configurable passed to server')
        self.assertFalse('stuff' in cpconfig.keys(), 'non-standard configurable passed to server')

        server.stop()

    def testMissingRequiredConfigParams(self):
        """
        All applications should define:
        ['admin', 'description', 'title']
        """
        config = self.getBaseConfiguration()

        config.UnitTests.__delattr__('admin')
        server = Root(config)
        self.assertRaises(AssertionError, server.start, blocking=False)

        config.UnitTests.admin = "Mr Unit Test"
        config.UnitTests.__delattr__('description')
        server = Root(config)
        self.assertRaises(AssertionError, server.start, blocking=False)

        config.UnitTests.description = "Dummy server for unit tests"
        config.UnitTests.__delattr__('title')
        server = Root(config)
        self.assertRaises(AssertionError, server.start, blocking=False)

    def testLongHandProxyBase(self):
        """
        Check that changing the proxy base via tools.proxy.base
        does actually change the proxy base
        """
        test_proxy_base = '/unit_test'

        config = self.getBaseConfiguration()
        config.Webtools.section_('tools')
        config.Webtools.tools.section_('proxy')
        config.Webtools.tools.proxy.base = test_proxy_base
        config.Webtools.tools.proxy.on = True
        server = Root(config)

        server.start(blocking=False)
        self.assertEquals(cpconfig['tools.proxy.base'], test_proxy_base)
        server.stop()

    def testShortHandProxyBase(self):
        """
        Check that changing the proxy_base via the short hand config variable
        does actually change the proxy base
        """
        test_proxy_base = '/unit_test'

        config = self.getBaseConfiguration()
        # Set the proxy base with a short hand cfg variable
        config.Webtools.proxy_base = test_proxy_base
        server = Root(config)

        server.start(blocking=False)
        self.assertEquals(cpconfig['tools.proxy.base'], test_proxy_base)
        server.stop()

    def testLongHandChangePort(self):
        """
        Change the port the server runs on long hand
        """
        test_port = 8010

        config = self.getBaseConfiguration()
        # Set the port to a non-standard one
        config.Webtools.section_('server')
        config.Webtools.server.socket_port = test_port

        server = Root(config)
        server.start(blocking=False)
        self.assertEquals(cpconfig['server.socket_port'], test_port)
        server.stop()

    def testShortHandChangePort(self):
        """
        Change the port the server runs on short hand
        """
        test_port = 8010

        config = self.getBaseConfiguration()
        # Set the port to a non-standard one
        config.Webtools.port = test_port

        server = Root(config)
        server.start(blocking=False)
        self.assertEquals(cpconfig['server.socket_port'], test_port)
        server.stop()

    def testShortHandPortOverride(self):
        """
        Change the port the server runs on long hand, then over ride
        it with the short hand equivalent
        """
        test_port = 8010

        config = self.getBaseConfiguration()
        # Set the port the long handed way
        config.Webtools.section_('server')
        config.Webtools.server.socket_port = test_port - 1
        # then override
        config.Webtools.port = test_port

        server = Root(config)
        server.start(blocking=False)
        self.assertEquals(cpconfig['server.socket_port'], test_port)
        server.stop()

    def testSecuritySetting(self):
        testRole = "TestRole"
        testGroup = "TestGroup"
        testSite = "TestSite"
        config = self.getBaseConfiguration()
        config.SecurityModule.dangerously_insecure = False
        # not real keyfile but for the test.
        # file will be deleted automaticall when garbage collected.
        tempFile = NamedTemporaryFile()
        config.SecurityModule.key_file = tempFile.name
        config.SecurityModule.section_("default")
        config.SecurityModule.default.role = testRole
        config.SecurityModule.default.group = testGroup
        config.SecurityModule.default.site = testSite
        config.Webtools.environment = "production"
        server = Root(config)
        server.start(blocking=False)
        self.assertEquals(cpconfig['tools.secmodv2.on'], True)
        self.assertEquals(cpconfig['tools.secmodv2.role'], testRole)
        self.assertEquals(cpconfig['tools.secmodv2.group'], testGroup)
        self.assertEquals(cpconfig['tools.secmodv2.site'], testSite)
        server.stop()

    def testInstanceInUrl(self):
        config = self.getBaseConfiguration()
        config.SecurityModule.dangerously_insecure = True
        server = Root(config)
        # Add our test page
        config.UnitTests.instances = ['foo', 'bar', 'baz/zoink']
        active = config.UnitTests.views.section_('active')
        active.section_('test')
        active.test.object = 'WMCore_t.WebTools_t.InstanceTestPage'
        active.test.section_('database')
        instances = active.test.database.section_('instances')
        foo = instances.section_('foo')
        bar = instances.section_('bar')
        baz = instances.section_('baz/zoink')
        foo.connectUrl = 'sqlite:///foo'
        bar.connectUrl = 'sqlite:///bar'
        baz.connectUrl = 'sqlite:///baz/zoink'
        server.start(blocking=False)

        for instance in config.UnitTests.instances:
            url = 'http://127.0.0.1:8888/unittests/%s/test' % instance
            html = urllib2.urlopen(url).read()
            self.assertEquals(html, instance)
            url = '%s/database' % url
            html = urllib2.urlopen(url).read()
            self.assertEquals(html, instances.section_(instance).connectUrl)
        server.stop()

    def testUsingFilterTool(self):
        """
        Use the filter tool to prevent unexpected accesses from
        unsupported methods
        TODO
        """
        pass

if __name__ == '__main__':
    unittest.main()
