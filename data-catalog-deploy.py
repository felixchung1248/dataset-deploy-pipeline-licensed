# Inlined from /metadata-ingestion/examples/library/dataset_schema.py
# Imports for urn construction utility methods
from datahub.emitter.mce_builder import make_data_platform_urn, make_user_urn,make_tag_urn
from datahub.emitter.mcp import MetadataChangeProposalWrapper
from datahub.emitter.rest_emitter import DatahubRestEmitter
# read-modify-write requires access to the DataHubGraph (RestEmitter is not enough)
from datahub.ingestion.graph.client import DatahubClientConfig, DataHubGraph
# Imports for metadata model classes
from datahub.metadata.schema_classes import (
    OwnerClass,
    OwnershipClass,
    OwnershipTypeClass,
    DatasetPropertiesClass,
    GlobalTagsClass,
    TagAssociationClass
)
import datahub.emitter.mce_builder as builder

import requests
import logging
import sys
from requests.auth import HTTPBasicAuth
import csv
from io import StringIO
from typing import Optional


# Imports for metadata model classes
from datahub.metadata.schema_classes import *

log = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def case1():
    return StringTypeClass()

def case2():
    return BooleanTypeClass()

def case3():
    return NumberTypeClass()

def case4():
    return DateTypeClass()

def case5():
    return TimeTypeClass()

# Function to parse key-value pairs from command line arguments
def parse_key_value_pairs(argv):
    params = {}
    for arg in argv[1:]:  # Skip the script name
        key, value = arg.split('=', 1)
        params[key] = value
    return params

parameters = parse_key_value_pairs(sys.argv)
# batchKey = parameters['batch_key']
ticketId = parameters['ticket_id']
# token = parameters['token']
zammad_usr = parameters['zammad_usr']
zammad_pw = parameters['zammad_pw']
zammad_url = parameters['zammad_url']
dataset = parameters['dataset']
datahub_url = parameters['datahub_url']
dataset_owner = parameters['dataset_owner']
dataset_description = parameters['dataset_description']

response = requests.get(
            f"{zammad_url}/api/v1/ticket_articles/by_ticket/{ticketId}",
            auth=HTTPBasicAuth(zammad_usr, zammad_pw)
        )

data = response.json()
articleId = data[0]['id']
attachments = data[0]['attachments']
attachmentId = attachments[0]['id']

response = requests.get(
            f"{zammad_url}/api/v1/ticket_attachment/{ticketId}/{articleId}/{attachmentId}",
            auth=HTTPBasicAuth(zammad_usr, zammad_pw)
        )

csv_content = response.text
# Parse the CSV content using StringIO and csv.reader
csv_reader = csv.reader(StringIO(csv_content))

# Skip the header row if your CSV has one (optional)
next(csv_reader, None)

switch_dict = {
            "string": case1,
            "boolean": case2,
            "number": case3
        }

fields = []
for row in csv_reader:
    name = row[0]
    description = row[1]
    data_type = row[3]
    is_sensitive = row[2]
    typeClass = switch_dict.get(data_type)()
    tagList = []
    if is_sensitive == 'True':
        tagList.append(TagAssociationClass(make_tag_urn('sensitive')))
        field = SchemaFieldClass(
                        fieldPath=name,
                        type=SchemaFieldDataTypeClass(type=typeClass),
                        nativeDataType=data_type,  # use this to provide the type of the field in the source system's vernacular
                        description=description,
                        lastModified=AuditStampClass(
                            time=1640692800000, actor="urn:li:corpuser:ingestion"
                        ),
                        globalTags=GlobalTagsClass(tagList)
                    )
    else:
        field = SchemaFieldClass(
                        fieldPath=name,
                        type=SchemaFieldDataTypeClass(type=typeClass),
                        nativeDataType=data_type,  # use this to provide the type of the field in the source system's vernacular
                        description=description,
                        lastModified=AuditStampClass(
                            time=1640692800000, actor="urn:li:corpuser:ingestion"
                        )
                    )
    fields.append(field)

owner_to_add = make_user_urn(dataset_owner)
ownership_type = OwnershipTypeClass.TECHNICAL_OWNER
dataset_urn=builder.make_dataset_urn(platform="Denodo", name=dataset, env="PROD")

owner_class_to_add = OwnerClass(owner=owner_to_add, type=ownership_type)
# owner_class_to_add = OwnerClass(owner=owner_to_add)
ownership_to_add = OwnershipClass(owners=[owner_class_to_add])

graph = DataHubGraph(DatahubClientConfig(server=datahub_url))

current_owners: Optional[OwnershipClass] = graph.get_aspect(
    entity_urn=dataset_urn, aspect_type=OwnershipClass
)

current_dataset_properties: Optional[DatasetPropertiesClass] = graph.get_dataset_properties(entity_urn=dataset_urn)

if current_dataset_properties is None:
    dataset_properties = DatasetPropertiesClass(description=dataset_description,
        customProperties={
         "rating": "-1"
        })
else:
    dataset_properties = DatasetPropertiesClass(description=dataset_description)


event: MetadataChangeProposalWrapper = MetadataChangeProposalWrapper(
    entityUrn=dataset_urn,
    aspect=SchemaMetadataClass(
        schemaName="customer",  # not used
        platform=make_data_platform_urn("Denodo"),  # important <- platform must be an urn
        version=0,  # when the source system has a notion of versioning of schemas, insert this in, otherwise leave as 0
        hash="",  # when the source system has a notion of unique schemas identified via hash, include a hash, else leave it as empty string
        platformSchema=OtherSchemaClass(rawSchema="__insert raw schema here__"),
        lastModified=AuditStampClass(
            time=1640692800000, actor="urn:li:corpuser:ingestion"
        ),
        fields=fields,
    ),
)
# Create rest emitter
rest_emitter = DatahubRestEmitter(gms_server=datahub_url)
rest_emitter.emit(event)

metadata_event = MetadataChangeProposalWrapper(
    entityUrn=dataset_urn,
    aspect=dataset_properties,
)

# Emit metadata! This is a blocking call
rest_emitter.emit(metadata_event)

need_write = False
if current_owners:
    if (owner_to_add, ownership_type) not in [
        (x.owner, x.type) for x in current_owners.owners
    ]:
        # owners exist, but this owner is not present in the current owners
        current_owners.owners.append(owner_class_to_add)
        need_write = True
else:
    # create a brand new ownership aspect
    current_owners = ownership_to_add
    need_write = True

if need_write:
    event: MetadataChangeProposalWrapper = MetadataChangeProposalWrapper(
        entityUrn=dataset_urn,
        aspect=current_owners,
    )
    graph.emit(event)
    log.info(
        f"Owner {owner_to_add}, type {ownership_type} added to dataset {dataset_urn}"
    )

else:
    log.info(f"Owner {owner_to_add} already exists, omitting write")


