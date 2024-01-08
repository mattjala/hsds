##############################################################################
# Copyright by The HDF Group.                                                #
# All rights reserved.                                                       #
#                                                                            #
# This file is part of HSDS (HDF5 Scalable Data Service), Libraries and      #
# Utilities.  The full HSDS copyright notice, including                      #
# terms governing use, modification, and redistribution, is contained in     #
# the file COPYING, which can be found at the root of the source code        #
# distribution tree.  If you do not have access to this file, you may        #
# request a copy from help@hdfgroup.org.                                     #
##############################################################################
from copy import copy
import unittest
import time
import json
import uuid
import helper
import config


class LinkTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(LinkTest, self).__init__(*args, **kwargs)
        self.base_domain = helper.getTestDomainName(self.__class__.__name__)
        helper.setupDomain(self.base_domain, folder=True)

    def setUp(self):
        self.session = helper.getSession()

    def tearDown(self):
        if self.session:
            self.session.close()

    def testHardLink(self):
        domain = self.base_domain + "/testHardLink.h5"
        print("testHardLink", domain)
        helper.setupDomain(domain)
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/"
        test_user2 = config.get("user2_name")  # some tests will be skipped if not set

        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        root_id = rspJson["root"]

        # get root group and check it has no links
        req = helper.getEndpoint() + "/groups/" + root_id
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], 0)  # no links

        # create a new group
        req = helper.getEndpoint() + "/groups"
        rsp = self.session.post(req, headers=headers)
        self.assertEqual(rsp.status_code, 201)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], 0)
        self.assertEqual(rspJson["attributeCount"], 0)
        grp1_id = rspJson["id"]
        self.assertTrue(helper.validateId(grp1_id))

        # try to get "/g1"  (doesn't exist yet)
        link_title = "g1"
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 404)  # link doesn't exist yet

        # try creating a link with a different user (should fail)
        if test_user2:
            headers = helper.getRequestHeaders(domain=domain, username=test_user2)
            payload = {"id": grp1_id}
            rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
            self.assertEqual(rsp.status_code, 403)  # forbidden
        else:
            print("test_user2 name not set")

        # create "/g1" with original user
        payload = {"id": grp1_id}
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)  # created

        # now gettting the link should succeed
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)  # should get link now
        rspJson = json.loads(rsp.text)
        self.assertTrue("created" in rspJson)
        self.assertTrue("lastModified" in rspJson)
        self.assertTrue("hrefs" in rspJson)
        self.assertTrue("link" in rspJson)
        rspLink = rspJson["link"]
        self.assertEqual(rspLink["title"], "g1")
        self.assertEqual(rspLink["class"], "H5L_TYPE_HARD")
        self.assertEqual(rspLink["id"], grp1_id)
        self.assertEqual(rspLink["collection"], "groups")

        # try creating the link again  (should be ok - PUT is idempotent)
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 200)  # OK

        # try creating a link with different target id
        payload = {"id": root_id}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 409)  # Conflict

        # get the root group and verify the link count is one
        req = helper.getEndpoint() + "/groups/" + root_id
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], 1)  # link count is 1

        # try deleting link with a different user (should fail)
        if test_user2:
            headers = helper.getRequestHeaders(domain=domain, username=test_user2)
            req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
            rsp = self.session.delete(req, headers=headers)
            self.assertEqual(rsp.status_code, 403)  # forbidden
        else:
            print("user2_name not set")

        # delete the link with original user
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.delete(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)

        # try creating a link with a bogus id
        fake_id = "g-" + str(uuid.uuid1())
        payload = {"id": fake_id}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 404)  # not found

        # try creating a link without a link name
        payload = {"id": grp1_id}
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/"
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 404)  # Not Found

        # try creating a link with a forward slash in link name
        link_title = "one/two"
        payload = {"id": grp1_id}
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 404)  # Not Found

        # try creating a link with a backward slash in link name
        link_title = "two\\one"
        payload = {"id": grp1_id}
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)  # Created

        # delete the link
        rsp = self.session.delete(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)

        # got a real id, but outside this domain
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/another_domain"
        another_domain = self.base_domain + "/testHardLink2.h5"
        helper.setupDomain(another_domain)
        another_id = helper.getRootUUID(another_domain, session=self.session)
        payload = {"id": another_id}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 400)  # Invalid request

        # try creating a link with a space in the title
        link_title = "name with spaces"
        payload = {"id": grp1_id}
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)  # Created
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)  # should get link now
        rspJson = json.loads(rsp.text)
        self.assertTrue("link" in rspJson)
        rspLink = rspJson["link"]
        self.assertEqual(rspLink["title"], link_title)
        rsp = self.session.delete(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)

        # get the root group and verify the link count is zero
        req = helper.getEndpoint() + "/groups/" + root_id
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], 0)  # link count should zero

    def testSoftLink(self):
        domain = self.base_domain + "/testSoftLink.h5"
        print("testSoftLink", domain)
        helper.setupDomain(domain)
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/"

        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        root_id = rspJson["root"]

        # get root group and check it has no links
        req = helper.getEndpoint() + "/groups/" + root_id
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], 0)  # no links

        # create softlink
        link_title = "softlink"
        target_path = "somewhere"
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        payload = {"h5path": target_path}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)  # created

        # get root group and check it has one link
        req = helper.getEndpoint() + "/groups/" + root_id
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], 1)  # no links

        # get the link
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)  # should get the softlink
        rspJson = json.loads(rsp.text)
        self.assertTrue("created" in rspJson)
        self.assertTrue("lastModified" in rspJson)
        self.assertTrue("hrefs" in rspJson)
        self.assertTrue("link" in rspJson)
        rspLink = rspJson["link"]
        self.assertEqual(rspLink["title"], link_title)
        self.assertEqual(rspLink["class"], "H5L_TYPE_SOFT")
        self.assertEqual(rspLink["h5path"], target_path)

    def testExternalLink(self):
        domain = self.base_domain + "/testExternalLink.h5"
        print("testExternalLink", domain)
        helper.setupDomain(domain)
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/"

        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        root_id = rspJson["root"]

        # get root group and check it has no links
        req = helper.getEndpoint() + "/groups/" + root_id
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], 0)  # no links

        # create external link
        target_domain = self.base_domain + "/external_target.h5"
        target_path = "somewhere"
        link_title = "external_link"
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        payload = {"h5path": target_path, "h5domain": target_domain}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)  # created

        # get root group and check it has one link
        req = helper.getEndpoint() + "/groups/" + root_id
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], 1)  # no links

        # get the link
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)  # should get the softlink
        rspJson = json.loads(rsp.text)
        self.assertTrue("created" in rspJson)
        self.assertTrue("lastModified" in rspJson)
        self.assertTrue("hrefs" in rspJson)
        self.assertTrue("link" in rspJson)
        rspLink = rspJson["link"]
        self.assertEqual(rspLink["title"], link_title)
        self.assertEqual(rspLink["class"], "H5L_TYPE_EXTERNAL")
        self.assertEqual(rspLink["h5path"], target_path)
        self.assertEqual(rspLink["h5domain"], target_domain)

    def testGetLinks(self):
        domain = self.base_domain + "/testGetLinks.h5"
        print("testGetLinks", domain)
        helper.setupDomain(domain)
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/"

        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        root_id = rspJson["root"]

        # get root group and check it has no links
        req = helper.getEndpoint() + "/groups/" + root_id
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], 0)  # no links

        link_names = [
            "first",
            "second",
            "third",
            "fourth",
            "fifth",
            "sixth",
            "seventh",
            "eighth",
            "ninth",
            "tenth",
            "eleventh",
            "twelfth",
        ]

        # create subgroups and link them to root using the above names
        for link_name in link_names:
            req = helper.getEndpoint() + "/groups"
            rsp = self.session.post(req, headers=headers)
            self.assertEqual(rsp.status_code, 201)
            rspJson = json.loads(rsp.text)
            grp_id = rspJson["id"]
            # link the new group
            req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_name
            payload = {"id": grp_id}
            rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
            self.assertEqual(rsp.status_code, 201)  # created

        # get the root group and verify the link count is correct
        req = helper.getEndpoint() + "/groups/" + root_id
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertEqual(rspJson["linkCount"], len(link_names))

        req = helper.getEndpoint() + "/groups/" + root_id + "/links"

        for creation_order in (False, True):

            # get all the links for the root group
            params = {}
            if creation_order:
                params["CreateOrder"] = 1
            rsp = self.session.get(req, params=params, headers=headers)
            self.assertEqual(rsp.status_code, 200)
            rspJson = json.loads(rsp.text)
            self.assertTrue("links" in rspJson)
            self.assertTrue("hrefs" in rspJson)
            links = rspJson["links"]
            self.assertEqual(len(links), len(link_names))
            ret_names = []
            for link in links:
                self.assertTrue("title" in link)
                self.assertTrue("class" in link)
                self.assertEqual(link["class"], "H5L_TYPE_HARD")
                self.assertTrue("collection" in link)
                self.assertEqual(link["collection"], "groups")
                self.assertTrue("created" in link)
                ret_names.append(link["title"])

            expected_names = copy(link_names)

            if creation_order:
                # result should come back in sorted order
                pass
            else:
                expected_names.sort()  # lexographic order
                #  sorted list should be:
                #  ['eighth', 'eleventh', 'fifth', 'first', 'fourth', 'ninth',
                #  'second', 'seventh', 'sixth', 'tenth', 'third', 'twelfth']
                #

            self.assertEqual(ret_names, expected_names)

            # get links with a result limit of 4
            limit = 4
            params = {"Limit": limit}
            if creation_order:
                params["CreateOrder"] = 1
            rsp = self.session.get(req, params=params, headers=headers)
            self.assertEqual(rsp.status_code, 200)
            rspJson = json.loads(rsp.text)
            self.assertTrue("links" in rspJson)
            self.assertTrue("hrefs" in rspJson)
            links = rspJson["links"]
            self.assertEqual(len(links), limit)
            last_link = links[-1]
            self.assertEqual(last_link["title"], expected_names[limit - 1])

            # get links after the one with name: "seventh"
            marker = "seventh"
            params = {"Marker": marker}
            if creation_order:
                params["CreateOrder"] = 1
            rsp = self.session.get(req, params=params, headers=headers)
            self.assertEqual(rsp.status_code, 200)
            rspJson = json.loads(rsp.text)
            self.assertTrue("links" in rspJson)
            self.assertTrue("hrefs" in rspJson)
            links = rspJson["links"]
            if creation_order:
                self.assertEqual(len(links), 5)
            else:
                self.assertEqual(len(links), 4)
            last_link = links[-1]
            # "twelfth" is last in either ordering
            self.assertEqual(last_link["title"], "twelfth")

            # Use a marker that is not present (should return 404)
            params["Marker"] = "foobar"
            rsp = self.session.get(req, params=params, headers=headers)
            self.assertEqual(rsp.status_code, 404)

            # get links starting with name: "seventh", and limit to 3 results
            params["Marker"] = "seventh"
            limit = 3
            params["Limit"] = limit
            rsp = self.session.get(req, params=params, headers=headers)
            self.assertEqual(rsp.status_code, 200)
            rspJson = json.loads(rsp.text)
            self.assertTrue("links" in rspJson)
            self.assertTrue("hrefs" in rspJson)
            links = rspJson["links"]
            self.assertEqual(len(links), 3)
            last_link = links[-1]
            if creation_order:
                # expecting: "eighth", "ninth", "tenth"
                self.assertEqual(last_link["title"], "tenth")
            else:
                # expecting: "sixth", "tenth", "third"
                self.assertEqual(last_link["title"], "third")

    def testGet(self):
        # test getting links from an existing domain
        domain = helper.getTestDomain("tall.h5")
        print("testGetDomain", domain)
        headers = helper.getRequestHeaders(domain=domain)

        # verify domain exists
        req = helper.getEndpoint() + "/"
        rsp = self.session.get(req, headers=headers)
        if rsp.status_code != 200:
            print(f"WARNING: Failed to get domain: {domain}. Is test data setup?")
            return  # abort rest of test

        rspJson = json.loads(rsp.text)
        root_uuid = rspJson["root"]
        self.assertTrue(root_uuid.startswith("g-"))

        # get the "/g1/g1.2" group
        g1_2_uuid = helper.getUUIDByPath(domain, "/g1/g1.2", session=self.session)

        now = time.time()

        # get links for /g1/g1.2:
        req = helper.getEndpoint() + "/groups/" + g1_2_uuid + "/links"
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertTrue("hrefs" in rspJson)
        hrefs = rspJson["hrefs"]
        self.assertEqual(len(hrefs), 3)
        self.assertTrue("links" in rspJson)
        links = rspJson["links"]
        self.assertEqual(len(links), 2)
        g1_2_1_uuid = None
        extlink_file = None
        for link in links:
            self.assertTrue("class" in link)
            link_class = link["class"]
            if link_class == "H5L_TYPE_HARD":
                for name in (
                    "target",
                    "created",
                    "collection",
                    "class",
                    "id",
                    "title",
                    "href",
                ):
                    self.assertTrue(name in link)
                g1_2_1_uuid = link["id"]
                self.assertTrue(g1_2_1_uuid.startswith("g-"))
                self.assertEqual(link["title"], "g1.2.1")
                self.assertTrue(link["created"] < now - 10)
            else:
                self.assertEqual(link_class, "H5L_TYPE_EXTERNAL")
                for name in ("created", "class", "h5domain", "h5path", "title", "href"):
                    self.assertTrue(name in link)
                self.assertEqual(link["title"], "extlink")
                extlink_file = link["h5domain"]
                self.assertEqual(extlink_file, "somefile")
                self.assertEqual(link["h5path"], "somepath")
                self.assertTrue(link["created"] < now - 10)

        self.assertTrue(g1_2_1_uuid is not None)
        self.assertTrue(extlink_file is not None)
        expected_uuid = helper.getUUIDByPath(domain, "/g1/g1.2/g1.2.1", session=self.session)
        self.assertEqual(expected_uuid, g1_2_1_uuid)

        # get link by title
        req = helper.getEndpoint() + "/groups/" + g1_2_1_uuid + "/links/slink"
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        for name in ("created", "lastModified", "link", "hrefs"):
            self.assertTrue(name in rspJson)
        # created should be same as lastModified for links
        self.assertEqual(rspJson["created"], rspJson["lastModified"])
        self.assertTrue(rspJson["created"] < now - 10)
        hrefs = rspJson["hrefs"]
        self.assertEqual(len(hrefs), 3)

        link = rspJson["link"]
        for name in ("title", "h5path", "class"):
            self.assertTrue(name in link)

        self.assertEqual(link["class"], "H5L_TYPE_SOFT")
        self.assertFalse("h5domain" in link)  # only for external links
        self.assertEqual(link["title"], "slink")
        self.assertEqual(link["h5path"], "somevalue")

    def testSoftLinkTraversal(self):
        # test that an object can be found via path with an external link
        # relative and absolute path

        domain = self.base_domain + "/testSoftLinkTraversal.h5"
        print("testSoftLinkTraversal", domain)
        helper.setupDomain(domain)
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/"

        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        root_id = rspJson["root"]

        # create group to be linked to by path
        req = helper.getEndpoint() + "/groups"
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.post(req, headers=headers)
        self.assertEqual(rsp.status_code, 201)
        rspJson = json.loads(rsp.text)
        group_id = rspJson["id"]
        self.assertTrue(helper.validateId(group_id))

        # create hard link to group
        link_title = "target_group"
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        headers = helper.getRequestHeaders(domain=domain)
        payload = {"id": group_id}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)  # created

        # create child of target group
        req = helper.getEndpoint() + "/groups"
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.post(req, headers=headers)
        self.assertEqual(rsp.status_code, 201)
        rspJson = json.loads(rsp.text)
        child_group_id = rspJson["id"]
        self.assertTrue(helper.validateId(child_group_id))

        # create hard link to child of external group
        link_title = "child_group"
        req = helper.getEndpoint() + "/groups/" + group_id + "/links/" + link_title
        headers = helper.getRequestHeaders(domain=domain)
        payload = {"id": child_group_id}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertTrue(rsp.status_code, 201)  # created

        # create soft link to parent group by absolute path
        target_path = "/target_group"
        link_title = "absolute_path_link"
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        payload = {"h5path": target_path}
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)

        # make a request by path with absolute path soft link along the way
        # request without 'follow soft links' param should receive 400
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/" + "?h5path=/absolute_path_link/child_group"
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 400)

        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/" + "?h5path=/absolute_path_link/child_group" \
            + "&follow_soft_links=1"
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        keys = ["domain", "linkCount", "attributeCount", "id"]
        for k in keys:
            self.assertTrue(k in rspJson)

        self.assertEqual(rspJson["id"], child_group_id)
        self.assertTrue(helper.validateId(rspJson["id"]))
        self.assertEqual(rspJson["domain"], domain)
        self.assertEqual(rspJson["linkCount"], 0)
        self.assertEqual(rspJson["attributeCount"], 0)
        self.assertEqual(rspJson["class"], "group")

        # create soft link to parent group by relative path
        target_path = "target_group"
        link_title = "relative_path_link"
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        payload = {"h5path": target_path}
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)

        # make a request by path with relative path soft link along the way
        # request without 'follow soft links' param should receive 400
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/" + "?h5path=/relative_path_link/child_group"
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 400)

        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/" + "?h5path=/relative_path_link/child_group" \
            + "&follow_soft_links=1"
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        keys = ["domain", "linkCount", "attributeCount", "id"]
        for k in keys:
            self.assertTrue(k in rspJson)

        self.assertEqual(rspJson["id"], child_group_id)
        self.assertTrue(helper.validateId(rspJson["id"]))
        self.assertEqual(rspJson["domain"], domain)
        self.assertEqual(rspJson["linkCount"], 0)
        self.assertEqual(rspJson["attributeCount"], 0)
        self.assertEqual(rspJson["class"], "group")

    def testExternalLinkTraversal(self):
        # test that an object can be found via path with an external link
        domain = self.base_domain + "/testExternalLinkTraversal.h5"
        print("testExternalLinkTraversal", domain)
        helper.setupDomain(domain)
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/"

        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        root_id = rspJson["root"]

        # create a second domain for external links to point to
        second_domain = self.base_domain + "/second_domain.h5"
        helper.setupDomain(second_domain)
        headers = helper.getRequestHeaders(domain=second_domain)
        req = helper.getEndpoint() + "/"
        rsp = self.session.put(req, headers=headers)
        self.assertTrue(rsp.status_code == 200 or rsp.status_code == 409)  # Created or exists

        # get root id of second domain
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        root_id_2 = rspJson["root"]

        # create a group under second domain
        req = helper.getEndpoint() + "/groups"
        headers = helper.getRequestHeaders(domain=second_domain)
        rsp = self.session.post(req, headers=headers)
        self.assertEqual(rsp.status_code, 201)
        rspJson = json.loads(rsp.text)
        group_id = rspJson["id"]
        self.assertTrue(helper.validateId(group_id))

        # create hard link to group
        link_title = "external_group"
        req = helper.getEndpoint() + "/groups/" + root_id_2 + "/links/" + link_title
        headers = helper.getRequestHeaders(domain=second_domain)
        payload = {"id": group_id}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)  # created

        # create child of external group
        req = helper.getEndpoint() + "/groups"
        headers = helper.getRequestHeaders(domain=second_domain)
        rsp = self.session.post(req, headers=headers)
        self.assertEqual(rsp.status_code, 201)
        rspJson = json.loads(rsp.text)
        child_group_id = rspJson["id"]
        self.assertTrue(helper.validateId(child_group_id))

        # create hard link to child of external group
        link_title = "child_group"
        req = helper.getEndpoint() + "/groups/" + group_id + "/links/" + link_title
        headers = helper.getRequestHeaders(domain=second_domain)
        payload = {"id": child_group_id}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertTrue(rsp.status_code, 201)  # created

        # create external link to parent group under a different domain
        target_path = "/external_group"
        link_title = "external_link_to_group"
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        payload = {"h5path": target_path, "h5domain": second_domain}
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)

        # make a request by path with external_link along the way
        # request without 'follow external links' param should receive 400
        headers = helper.getRequestHeaders(domain=domain)
        h5path = f"/{link_title}/child_group"
        req = helper.getEndpoint() + "/"
        params = {"h5path": h5path}
        rsp = self.session.get(req, headers=headers, params=params)
        self.assertEqual(rsp.status_code, 400)

        params["follow_external_links"] = 1
        rsp = self.session.get(req, headers=headers, params=params)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        keys = ["domain", "linkCount", "attributeCount", "id"]
        for k in keys:
            self.assertTrue(k in rspJson)

        self.assertEqual(rspJson["id"], child_group_id)
        self.assertTrue(helper.validateId(rspJson["id"]))
        self.assertEqual(rspJson["domain"], second_domain)
        self.assertEqual(rspJson["linkCount"], 0)
        self.assertEqual(rspJson["attributeCount"], 0)
        self.assertEqual(rspJson["class"], "group")

        # create external link with same target but using "hdf5://" prefix
        target_path = "/external_group"
        link_title = "external_link_to_group_prefix"
        req = helper.getEndpoint() + "/groups/" + root_id + "/links/" + link_title
        payload = {"h5path": target_path, "h5domain": f"hdf5:/{second_domain}"}
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 201)

        # make a request by path with external_link along the way
        # request without 'follow external links' param should receive 400
        headers = helper.getRequestHeaders(domain=domain)
        h5path = f"/{link_title}/child_group"
        req = helper.getEndpoint() + "/"
        params = {"h5path": h5path}
        rsp = self.session.get(req, headers=headers, params=params)
        self.assertEqual(rsp.status_code, 400)

        params["follow_external_links"] = 1
        rsp = self.session.get(req, headers=headers, params=params)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        keys = ["domain", "linkCount", "attributeCount", "id"]
        for k in keys:
            self.assertTrue(k in rspJson)

        self.assertEqual(rspJson["id"], child_group_id)
        self.assertTrue(helper.validateId(rspJson["id"]))
        self.assertEqual(rspJson["domain"], second_domain)
        self.assertEqual(rspJson["linkCount"], 0)
        self.assertEqual(rspJson["attributeCount"], 0)
        self.assertEqual(rspJson["class"], "group")

    def testRelativeH5Path(self):
        # test that an object can be found via h5path request to domain endpoint
        domain = self.base_domain + "/testRelativeH5Path.h5"
        print("testRelativeH5Path", domain)
        helper.setupDomain(domain)
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/"

        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)

        # create parent group
        req = helper.getEndpoint() + "/groups"
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.post(req, headers=headers)
        self.assertEqual(rsp.status_code, 201)
        rspJson = json.loads(rsp.text)
        group_id = rspJson["id"]
        self.assertTrue(helper.validateId(group_id))

        # create child group
        req = helper.getEndpoint() + "/groups"
        headers = helper.getRequestHeaders(domain=domain)
        rsp = self.session.post(req, headers=headers)
        self.assertEqual(rsp.status_code, 201)
        rspJson = json.loads(rsp.text)
        child_group_id = rspJson["id"]
        self.assertTrue(helper.validateId(child_group_id))

        # create hard link to child of external group
        link_title = "child_group"
        req = helper.getEndpoint() + "/groups/" + group_id + "/links/" + link_title
        headers = helper.getRequestHeaders(domain=domain)
        payload = {"id": child_group_id}
        rsp = self.session.put(req, data=json.dumps(payload), headers=headers)
        self.assertTrue(rsp.status_code, 201)  # created

        # make a request by relative h5path
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/" + "?h5path=child_group&parent_id=" + group_id
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        keys = ["domain", "linkCount", "attributeCount", "id"]
        for k in keys:
            self.assertTrue(k in rspJson)

        self.assertEqual(rspJson["id"], child_group_id)
        self.assertTrue(helper.validateId(rspJson["id"]))
        self.assertEqual(rspJson["domain"], domain)
        self.assertEqual(rspJson["linkCount"], 0)
        self.assertEqual(rspJson["attributeCount"], 0)
        self.assertEqual(rspJson["class"], "group")

    def testRootH5Path(self):
        # test that root group can be found by h5path
        creation_props = {"link_creation_order": True, "rdcc_nbytes": 1024}
        domain = self.base_domain + "/testRootH5Path.h5"
        print("testRootH5Path", domain)
        helper.setupDomain(domain, root_gcpl=creation_props)
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/"

        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        root_id = rspJson["root"]

        # make a request by h5path
        headers = helper.getRequestHeaders(domain=domain)
        req = helper.getEndpoint() + "/" + "?h5path=/"
        rsp = self.session.get(req, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        keys = ["domain", "linkCount", "attributeCount", "id"]
        for k in keys:
            self.assertTrue(k in rspJson)

        self.assertEqual(rspJson["id"], root_id)
        self.assertTrue(helper.validateId(rspJson["id"]))
        self.assertEqual(rspJson["domain"], domain)
        self.assertEqual(rspJson["linkCount"], 0)
        self.assertEqual(rspJson["attributeCount"], 0)
        self.assertEqual(rspJson["class"], "group")

        cprops = rspJson["creationProperties"]
        for k in ("link_creation_order", "rdcc_nbytes"):
            self.assertTrue(k in cprops)
            self.assertEqual(cprops[k], creation_props[k])

    def testPostLinkSingle(self):
        domain = helper.getTestDomain("tall.h5")
        print("testPostLinkSingle", domain)
        headers = helper.getRequestHeaders(domain=domain)
        headers["Origin"] = "https://www.hdfgroup.org"  # test CORS

        # verify domain exists
        req = helper.getEndpoint() + "/"
        rsp = self.session.get(req, headers=headers)
        if rsp.status_code != 200:
            msg = f"WARNING: Failed to get domain: {domain}. Is test data setup?"
            print(msg)
            return  # abort rest of test

        domainJson = json.loads(rsp.text)
        root_id = domainJson["root"]
        helper.validateId(root_id)

        # get the "/g1/g1.2" group
        g1_2_uuid = helper.getUUIDByPath(domain, "/g1/g1.2", session=self.session)

        now = time.time()

        # get link "extlink" and "g1.2.1" for /g1/g1.2:
        titles = ["extlink", "g1.2.1"]
        payload = {"titles": titles}
        req = helper.getEndpoint() + "/groups/" + g1_2_uuid + "/links"
        rsp = self.session.post(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertTrue("links" in rspJson)
        links = rspJson["links"]
        self.assertEqual(len(links), 2)
        g1_2_1_uuid = None
        extlink_file = None
        for link in links:
            self.assertTrue("class" in link)
            link_class = link["class"]
            if link_class == "H5L_TYPE_HARD":
                for name in (
                    "created",
                    "class",
                    "id",
                    "title",
                ):
                    self.assertTrue(name in link)
                g1_2_1_uuid = link["id"]
                self.assertTrue(g1_2_1_uuid.startswith("g-"))
                self.assertEqual(link["title"], "g1.2.1")
                self.assertTrue(link["created"] < now - 10)
            else:
                self.assertEqual(link_class, "H5L_TYPE_EXTERNAL")
                for name in ("created", "class", "h5domain", "h5path", "title"):
                    self.assertTrue(name in link)
                self.assertEqual(link["title"], "extlink")
                extlink_file = link["h5domain"]
                self.assertEqual(extlink_file, "somefile")
                self.assertEqual(link["h5path"], "somepath")
                self.assertTrue(link["created"] < now - 10)

        self.assertTrue(g1_2_1_uuid is not None)
        self.assertTrue(extlink_file is not None)
        expected_uuid = helper.getUUIDByPath(domain, "/g1/g1.2/g1.2.1", session=self.session)
        self.assertEqual(expected_uuid, g1_2_1_uuid)

    def testPostLinkMultiple(self):
        domain = helper.getTestDomain("tall.h5")
        print("testPostLinkSingle", domain)
        headers = helper.getRequestHeaders(domain=domain)
        headers["Origin"] = "https://www.hdfgroup.org"  # test CORS

        # verify domain exists
        req = helper.getEndpoint() + "/"
        rsp = self.session.get(req, headers=headers)
        if rsp.status_code != 200:
            msg = f"WARNING: Failed to get domain: {domain}. Is test data setup?"
            print(msg)
            return  # abort rest of test

        domainJson = json.loads(rsp.text)
        root_id = domainJson["root"]
        helper.validateId(root_id)

        # get the "/g1/g1.2" group
        h5paths = ["/g1", "/g2", "/g1/g1.1", "/g1/g1.2", "/g2", "/g1/g1.2/g1.2.1"]
        grp_map = {}
        g1_id = None
        g2_id = None
        for h5path in h5paths:
            grp_id = helper.getUUIDByPath(domain, h5path, session=self.session)
            grp_map[grp_id] = h5path
            if h5path == "/g1":
                g1_id = grp_id  # save
            elif h5path == "/g2":
                g2_id = grp_id

        # get all links for the given set of group ids
        grp_ids = list(grp_map.keys())
        payload = {"group_ids": grp_ids}
        req = helper.getEndpoint() + "/groups/" + root_id + "/links"
        rsp = self.session.post(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertTrue("links" in rspJson)
        obj_links = rspJson["links"]
        self.assertTrue(len(obj_links), len(grp_ids))
        for grp_id in obj_links:
            self.assertTrue(grp_id in grp_map)
            h5path = grp_map[grp_id]
            if h5path == "/g1/g1.2/g1.2.1":
                expected_count = 1
            else:
                expected_count = 2  # all the rest have two links
            links = obj_links[grp_id]
            self.assertEqual(len(links), expected_count)
            for link in links:
                title = link["title"]
                expected = helper.getLink(domain, grp_id, title)
                self.assertEqual(link["class"], expected["class"])
                link_class = link["class"]
                if link_class == "H5L_TYPE_HARD":
                    self.assertEqual(link["id"], expected["id"])
                else:
                    # soft or external link
                    self.assertEqual(link["h5path"], expected["h5path"])
                    if link_class == "H5L_TYPE_EXTERNAL":
                        self.assertEqual(link["h5domain"], expected["h5domain"])

        # get just the request links for each group
        link_map = {g1_id: ["g1.1", "g1.2"], g2_id: ["dset2.2", ]}
        payload = {"group_ids": link_map}
        rsp = self.session.post(req, data=json.dumps(payload), headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertTrue("links" in rspJson)
        obj_links = rspJson["links"]
        self.assertEqual(len(obj_links), 2)
        self.assertTrue(g1_id in obj_links)
        g1_links = obj_links[g1_id]
        self.assertEqual(len(g1_links), 2)
        for link in g1_links:
            self.assertTrue("class" in link)
            self.assertEqual(link["class"], "H5L_TYPE_HARD")
            self.assertTrue("title" in link)
            self.assertTrue(link["title"] in ("g1.1", "g1.2"))
            self.assertTrue("id" in link)
        g2_links = obj_links[g2_id]
        self.assertEqual(len(g2_links), 1)  # two links in this group but just asked for dset2.2
        link = g2_links[0]
        self.assertEqual(link["class"], "H5L_TYPE_HARD")

        # get all links for the domain by providing the root_id with the follow_links param
        params = {"follow_links": 1}
        grp_ids = [root_id, ]
        payload = {"group_ids": grp_ids}
        rsp = self.session.post(req, data=json.dumps(payload), params=params, headers=headers)
        self.assertEqual(rsp.status_code, 200)
        rspJson = json.loads(rsp.text)
        self.assertTrue("links" in rspJson)
        obj_links = rspJson["links"]
        self.assertEqual(len(obj_links), 6)
        expected_group_links = ("g1", "g2", "g1.1", "g1.2", "g1.2.1", )
        expected_dset_links = ("dset1.2", "dset2.2", "dset1.1.1", "dset1.1.2", "dset2.1", )
        expected_soft_links = ("slink",)
        expected_external_links = ("extlink", )

        # listify the returned links
        links = []
        for obj_id in obj_links:
            links.extend(obj_links[obj_id])
        self.assertEqual(len(links), 11)
        for link in links:
            self.assertTrue("title" in link)
            title = link["title"]
            self.assertTrue("class" in link)
            link_class = link["class"]
            if link_class == "H5L_TYPE_HARD":
                link_id = link["id"]
                if link_id.startswith("g-"):
                    self.assertTrue(title in expected_group_links)
                elif link_id.startswith("d-"):
                    self.assertTrue(title in expected_dset_links)
                else:
                    self.assertTrue(False)  # unexpected
            elif link_class == "H5L_TYPE_SOFT":
                self.assertTrue(title in expected_soft_links)
            elif link_class == "H5L_TYPE_EXTERNAL":
                self.assertTrue(title in expected_external_links)
            else:
                self.assertTrue(False)  # unexpected


if __name__ == "__main__":
    # setup test files

    unittest.main()
