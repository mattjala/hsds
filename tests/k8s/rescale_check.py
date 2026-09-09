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

"""Write a chunked dataset, then read it back after a rescale.

getObjPartition() is hash(obj_id) % dn_count, so changing the data node count
remaps nearly every chunk. Nodes holding different rosters route the same id to
different data nodes, giving a wrong or missing chunk rather than a 503.

Run with the integ env vars set and HSDS_ENDPOINT pointing at the cluster:
    python tests/k8s/rescale_check.py write
    python tests/k8s/rescale_check.py read
"""

import json
import os
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "integ"))

import config  # noqa: E402
import helper  # noqa: E402

DSET_NAME = "rescale_probe"
NUM_ELEMENTS = 4000
CHUNK_ELEMENTS = 100  # 40 chunks, spread over the dn roster rather than one node


def domain_name():
    return f"/home/{config.get('user_name')}/hsds_test/k8s_rescale.h5"


def expected():
    return [i * 3 for i in range(NUM_ELEMENTS)]


def write():
    domain = domain_name()
    helper.setupDomain(domain)
    endpoint = helper.getEndpoint()
    headers = helper.getRequestHeaders(domain=domain)

    with helper.getSession() as session:
        root_uuid = helper.getRootUUID(domain, session=session)
        if not root_uuid:
            raise SystemExit(f"could not get root uuid for {domain}")

        payload = {
            "type": "H5T_STD_I32LE",
            "shape": [NUM_ELEMENTS],
            "creationProperties": {
                "layout": {"class": "H5D_CHUNKED", "dims": [CHUNK_ELEMENTS]},
            },
        }
        rsp = session.post(
            endpoint + "/datasets", data=json.dumps(payload), headers=headers
        )
        if rsp.status_code != 201:
            raise SystemExit(f"create dataset failed: {rsp.status_code} {rsp.text}")
        dset_uuid = json.loads(rsp.text)["id"]

        req = f"{endpoint}/groups/{root_uuid}/links/{DSET_NAME}"
        rsp = session.put(req, data=json.dumps({"id": dset_uuid}), headers=headers)
        if rsp.status_code != 201:
            raise SystemExit(f"link dataset failed: {rsp.status_code} {rsp.text}")

        req = f"{endpoint}/datasets/{dset_uuid}/value"
        rsp = session.put(
            req, data=json.dumps({"value": expected()}), headers=headers
        )
        if rsp.status_code != 200:
            raise SystemExit(f"write values failed: {rsp.status_code} {rsp.text}")

    print(f"wrote {NUM_ELEMENTS} elements in {NUM_ELEMENTS // CHUNK_ELEMENTS} "
          f"chunks to {domain}/{DSET_NAME}")


def read():
    domain = domain_name()
    endpoint = helper.getEndpoint()
    headers = helper.getRequestHeaders(domain=domain)

    with helper.getSession() as session:
        dset_uuid = helper.getUUIDByPath(domain, f"/{DSET_NAME}", session=session)
        if not dset_uuid:
            raise SystemExit(f"dataset {DSET_NAME} not found in {domain}")

        req = f"{endpoint}/datasets/{dset_uuid}/value"
        rsp = session.get(req, headers=headers)
        if rsp.status_code != 200:
            raise SystemExit(f"read values failed: {rsp.status_code} {rsp.text}")
        values = json.loads(rsp.text)["value"]

    want = expected()
    if len(values) != len(want):
        raise SystemExit(f"length mismatch: got {len(values)}, expected {len(want)}")
    for i, (got, exp) in enumerate(zip(values, want)):
        if got != exp:
            raise SystemExit(
                f"value mismatch at index {i}: got {got}, expected {exp} "
                f"(chunk {i // CHUNK_ELEMENTS})"
            )

    print(f"verified {len(values)} elements after rescale")


def main():
    if len(sys.argv) != 2 or sys.argv[1] not in ("write", "read"):
        raise SystemExit("usage: rescale_check.py write|read")
    if sys.argv[1] == "write":
        write()
    else:
        read()


if __name__ == "__main__":
    main()
