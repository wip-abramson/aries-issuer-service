import os
import requests
import logging
import json
import sys
import time
import asyncio
from aries_cloudcontroller import AriesAgentController
from datetime import date
import nest_asyncio

nest_asyncio.apply()

root = logging.getLogger()
root.setLevel(logging.DEBUG)

handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.DEBUG)
formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
handler.setFormatter(formatter)
root.addHandler(handler)




schema_id = 'W4t2Pa4XR1qBDvwhVcn4CY:2:Aries ACA ACC Jupyter Playground Demo Participation:0.0.1'
cred_def_id = None

api_key = os.getenv("ACAPY_ADMIN_API_KEY")
admin_url = os.getenv("ADMIN_URL")

agent_controller = AriesAgentController(admin_url,api_key)

def cred_handler(payload):
    connection_id = payload['connection_id']
    exchange_id = payload['credential_exchange_id']
    state = payload['state']
    role = payload['role']
    print("\n---------------------------------------------------\n")
    print("Handle Issue Credential Webhook")
    print(f"Connection ID : {connection_id}")
    print(f"Credential exchange ID : {exchange_id}")
    print("Agent Protocol Role : ", role)
    print("Protocol State : ", state)
    print("\n---------------------------------------------------\n")
    loop = asyncio.get_event_loop()
    if state == "proposal_received":
        print(f'Proposal Comment : {payload["credential_proposal_dict"]["comment"]}')
        proposed_cred_def_id = payload["credential_proposal_dict"]["cred_def_id"]
        proposed_schema_id = payload["credential_proposal_dict"]["schema_id"]

        if proposed_cred_def_id == cred_def_id and proposed_schema_id == schema_id:
            participant = None
            description = None
            for attribute in payload["credential_proposal_dict"]["credential_proposal"]["attributes"]:
                if attribute["name"] == "Participant":
                    participant = attribute["value"]
                elif attribute["name"] == "Description":
                    description = attribute["value"]
                    description += "\n Thanks for attending!"

            event_name = "Hyperledger Global Forum 2021"
            issue_date = date.today().isoformat()
            credential_attributes = [
                {"name": "Event Name", "value": event_name},
                {"name": "Participant", "value": participant},
                {"name": "Description", "value": description},
                {"name": "Date", "value": issue_date}
            ]

            print(credential_attributes)

            # Do you want the ACA-Py instance to trace it's processes (for testing/timing analysis)
            trace = False
            comment = ""
            # Remove credential record after issued?
            auto_remove = True

            # Change <schema_id> and <cred_def_id> to correct pair. Cred_def_id must identify a definition to which your agent has corresponding private issuing key.
            loop.run_until_complete(
                agent_controller.issuer.send_credential(connection_id, schema_id, cred_def_id, credential_attributes,
                                                        comment, auto_remove, trace))
        else:
            explanation = "You have not referenced the correct schema and credential definitions"
            loop.run_until_complete(agent_controller.issuer.send_problem_report(exchange_id, explanation))


cred_listener = {
    "topic": "issue_credential",
    "handler": cred_handler
}


def connections_handler(payload):
    state = payload['state']
    connection_id = payload["connection_id"]
    their_role = payload["their_role"]
    routing_state = payload["routing_state"]

    print("----------------------------------------------------------")
    print("Connection Webhook Event Received")
    print("Connection ID : ", connection_id)
    print("State : ", state)
    print("Routing State : ", routing_state)
    print("Their Role : ", their_role)
    print("----------------------------------------------------------")

    print(payload)

    if state == "active":
        # Your business logic
        print("Connection ID: {0} is now active.".format(connection_id))


connection_listener = {
    "handler": connections_handler,
    "topic": "connections"
}


async def initialise():
    print("INITIALISING THE AGENT")
    webhook_port = int(os.getenv("WEBHOOK_PORT"))
    webhook_host = "0.0.0.0"

    await agent_controller.init_webhook_server(webhook_host, webhook_port)

    print(f"Listening for webhooks from agent at http://{webhook_host}:{webhook_port}")

    agent_controller.register_listeners([cred_listener, connection_listener], defaults=True)

    is_alive = False
    while not is_alive:
        try:
            await agent_controller.server.get_status()
            is_alive = True
            logging.info("Agent Active")
        except:
            time.sleep(5)

    response = await agent_controller.wallet.get_public_did()

    print("PUBLIC DID", response)
    if not response['result']:
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