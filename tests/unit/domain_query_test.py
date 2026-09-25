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
import logging
import sys
import time
import unittest
from unittest.mock import patch

sys.path.append("../..")
from hsds.domain_sn import _checkQuerySyntax


class DomainQueryTest(unittest.TestCase):
    def __init__(self, *args, **kwargs):
        super(DomainQueryTest, self).__init__(*args, **kwargs)
        self.logger = logging.getLogger()
        self.logger.setLevel(logging.WARNING)

    def testValidQueries(self):
        # attribute names don't have to exist anywhere to be syntactically valid
        queries = (
            "attr1 > 7",
            "no_such_attr > 7",
            "no_such_attr == 'abc'",
            "attr1 > 7 AND attr2 != 'A0000004'",
            "(a > 1) | ~(b IN (x, y))",
            "field('weird name') > 3",
            "sym.isin('AAPL', 'EBAY')",
            "_ > 1",
            # a name that looks like the parser's own error text
            "field('x not found in dtype') > 1 AND y > 2",
        )
        for query in queries:
            _checkQuerySyntax(query)  # doesn't raise

    def testInvalidQueries(self):
        # These fail on the grammar. Several name unknown attributes before the
        # error, which is the case the check exists for: if the h5json internals
        # it relies on go away it skips itself, and these would stop raising.
        queries = (
            "no_such_attr > 7 AND",
            "no_such_attr == 'abc' AND attr1 >",
            "(no_such_attr > 7",
            "attr1 > 7 AND no_such_attr >",
            "a > 1 where b",
            "a >> 1",
            "field('x not found in dtype') > 1 AND y >",
            "field('') > 1",
        )
        for query in queries:
            with self.assertRaises(ValueError, msg=query):
                _checkQuerySyntax(query)

    def testManyNames(self):
        # the query is parsed once however many attributes it names, so a long
        # query can't tie up the service node
        names = [f"attr{i}" for i in range(2000)]
        query = " OR ".join(f"{name} > 1" for name in names)
        start = time.time()
        _checkQuerySyntax(query)
        self.assertLess(time.time() - start, 1.0)
        with self.assertRaises(ValueError):
            _checkQuerySyntax(query + " OR")

    def testParserFailureSkipsCheck(self):
        # anything but a ValueError means the h5json internals changed under us;
        # skip the check rather than rejecting every query
        with patch("h5json.query_util._Parser", side_effect=TypeError("changed")):
            _checkQuerySyntax("attr1 > 7 AND")  # doesn't raise


if __name__ == "__main__":
    # setup test files

    unittest.main()
