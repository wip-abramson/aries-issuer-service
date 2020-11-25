import os
import requests
import logging
import json
import sys
import time
import asyncio
from aries_basic_controller import AriesAgentController

root = logging.getLogger()
root.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)



WEBHOOK_HOST = os.getenv('WEBHOOK_HOST')
WEBHOOK_PORT = os.getenv('WEBHOOK_PORT')
WEBHOOK_BASE = os.getenv('WEBHOOK_BASE')
ADMIN_URL = os.getenv('ADMIN_URL')

root.info(f"Initialising Agent. Webhook URL {WEBHOOK_HOST}:{WEBHOOK_PORT}{WEBHOOK_BASE}. ADMIN_URL - {ADMIN_URL}")


schema_id = "D4zNtr48UJy7MdbsupTKbF:2:SSI Duet Tutorial:0.0.1"
cred_def_id = None

agent_controller = AriesAgentController(webhook_host=WEBHOOK_HOST, webhook_port=WEBHOOK_PORT,
                                       webhook_base=WEBHOOK_BASE, admin_url=ADMIN_URL)


def cred_handler(payload):
    print("Handle Credentials")
    exchange_id = payload['credential_exchange_id']
    state = payload['state']
    role = payload['role']
    attributes = payload['credential_proposal_dict']['credential_proposal']['attributes']
    print(f"Credential exchange {exchange_id}, role: {role}, state: {state}")
    print(f"Offering: {attributes}")


cred_listener = {
    "topic": "issue_credential",
    "handler": cred_handler
}


def connections_handler(payload):
    global STATE
    connection_id = payload["connection_id"]
    print("Connection message", payload, connection_id)
    STATE = payload['state']
    if STATE == 'active':
        #         print('Connection {0} changed state to active'.format(connection_id))
        root.info("Connection {0} changed state to active".format(connection_id))

        credential_attributes = [
            {"name": "connection_permitted", "value": "1"}
        ]
        loop = asyncio.get_event_loop()
        loop.create_task(
            agent_controller.issuer.send_credential(connection_id, schema_id, cred_def_id, credential_attributes,
                                                    trace=False))


connection_listener = {
    "handler": connections_handler,
    "topic": "connections"
}


async def initialise():
    print("INITIALISING THE AGENT")
    await agent_controller.listen_webhooks()

    agent_controller.register_listeners([cred_listener, connection_listener], defaults=True)

    is_alive = False
    while not is_alive:
        try:
            await agent_controller.server.get_status()
            is_alive = True
            logging.info("Agent Active")
        except:
            time.sleep(5)

    # response = await agent_controller.wallet.get_public_did()
    #
    # print("PUBLIC DID", response)
    # if not response['result']:
    did = await write_public_did()
    print(f"Public DID {did} written to the ledger")


    # Write Cred Def and Schema to ledger
    response = await agent_controller.definitions.write_cred_def(schema_id)

    global cred_def_id
    cred_def_id = response["credential_definition_id"]
    logging.info(f"Credential Definition {cred_def_id} for schema {schema_id}")

    # Create Invitation
    invite = await agent_controller.connections.create_invitation(multi_use="true")
    logging.info("Multi Use Connection Invitation")
    logging.info(invite["invitation"])


async def write_public_did():
    # generate new DID
    response = await agent_controller.wallet.create_did()

    did_object = response['result']
    did = did_object["did"]
    logging.debug("New DID", did)
    # write new DID to Sovrin Stagingnet

    url = 'https://selfserve.sovrin.org/nym'

    payload = {"network": "stagingnet", "did": did_object["did"], "verkey": did_object["verkey"], "paymentaddr": ""}

    # Adding empty header as parameters are being sent in payload
    headers = {}

    r = requests.post(url, data=json.dumps(payload), headers=headers)
    if r.status_code != 200:
        logging.error("Unable to write DID to StagingNet")
        raise Exception

    response = await agent_controller.ledger.get_taa()
    taa = response['result']['taa_record']
    taa['mechanism'] = "service_agreement"

    await agent_controller.ledger.accept_taa(taa)

    await agent_controller.wallet.assign_public_did(did)

    return did_object["did"]


loop = asyncio.get_event_loop()
loop.run_until_complete(initialise())



loop = asyncio.get_event_loop()
try:
    loop.run_forever()
finally:
    loop.close()