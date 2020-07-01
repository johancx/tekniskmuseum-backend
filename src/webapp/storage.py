"""
    Tools for interacting with Azure blob storage.
"""
import os
import uuid
import sys
from azure.storage.blob import BlobClient

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utilities.keys import Keys  # noqa: E402


def save_image(image, label):
    """
        Upload image to blob storage container with same name as image label.
        Image is renamed to assure unique name. Returns public URL to access
        image.
    """
    file_name = label + uuid.uuid4().hex + ".png"
    connection_string = Keys.get("BLOB_CONNECTION_STRING")
    container_name = "new-" + label
    base_url = Keys.get("BASE_BLOB_URL")
    try:
        blob = BlobClient.from_connection_string(
            conn_str=connection_string,
            container_name=container_name,
            blob_name=file_name,
        )
        blob.upload_blob(image)
    except Exception as e:
        print(e)
    url = base_url + "/" + container_name + "/" + file_name
    return url