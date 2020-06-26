from msrest.authentication import ApiKeyCredentials
from azure.storage.blob import BlobServiceClient
from azure.cognitiveservices.vision.customvision.prediction import (
    CustomVisionPredictionClient,
)
from azure.cognitiveservices.vision.customvision.training import (
    CustomVisionTrainingClient,
)
from azure.cognitiveservices.vision.customvision.training.models import (
    ImageUrlCreateEntry,
)
import uuid
import time

import sys
import os

from typing import Dict, List

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import keys  # noqa: e402


ENDPOINT = keys.get("ENDPOINT")
connect_str = keys.get("CONNECT_STR")
project_id = keys.get("PROJECT_ID")
prediction_key = keys.get("PREDICTION_KEY")
training_key = keys.get("TRAINING_KEY")
base_img_url = keys.get("BASE_IMG_URL")
prediction_resource_id = keys.get("PREDICTION_RESOURCE_ID")


class CVClassifier:

    def __init__(self, blob_service_client: BlobServiceClient) -> None:
        '''
        Reads configuration file
        Initializes connection to Azure Custom Vision predictor and training resources.

        Parameters:
        blob_service_client: Azure Blob Service interaction client

        Returns:
        None
        '''

        self.prediction_credentials = ApiKeyCredentials(
            in_headers={"Prediction-key": prediction_key}
        )
        self.predictor = CustomVisionPredictionClient(
            ENDPOINT, self.prediction_credentials
        )
        self.training_credentials = ApiKeyCredentials(
            in_headers={"Training-key": training_key}
        )
        self.trainer = CustomVisionTrainingClient(
            ENDPOINT, self.training_credentials
        )
        self.blob_service_client = blob_service_client
        iterations = self.trainer.get_iterations(project_id)
        iterations.sort(key=lambda i: i.created)
        self.iteration_name = iterations[-1].publish_name

    def predict(self, img_url: str) -> Dict[str, float]:
        '''
        Predicts label(s) of Image read from URL.

        Parameters:
        img_url: Image URL

        Returns:
        prediction (dict[str,float]): labels and assosiated probabilities
        '''

        res = self.predictor.classify_image_url(
            project_id, self.iteration_name, img_url
        )

        pred_kv = dict([(i.tag_name, i.probability) for i in res.predictions])

        return pred_kv

    def __chunks(self, lst, n):
        """Helper method used by upload_images() to upload URL chunks of 64, which is maximum chunk size in Azure Custom Vision."""
        for i in range(0, len(lst), n):
            yield lst[i: i + n]

    def upload_images(self, labels: List) -> None:
        """
        Takes as input a list of labels, uploads all assosiated images to Azure Custom Vision project.
        If label in input already exists in Custom Vision project, all images are uploaded directly.
        If label in input does not exist in Custom Vision project, new label (Tag object in Custom Vision) is created before uploading images


        Parameters:
        labels (str[]): List of labels

        Returns:
        None
        """

        url_list = []
        existing_tags = self.trainer.get_tags(project_id)

        # create list of URLs to be uploaded
        for label in labels:

            # check if input has correct type
            if not isinstance(label, str):
                raise Exception("label " + str(label) + " must be a string")

            tag = [t for t in existing_tags if t.name == label]

            # check if tag already exists
            if len(tag) == 0:

                try:
                    tag = self.trainer.create_tag(project_id, label)
                    print("Created new label in project: " + label)
                except Exception as e:
                    print(e)
                    continue

            else:
                tag = tag[0]

            try:
                container = self.blob_service_client.get_container_client(
                    str(label)
                )
            except Exception as e:
                print(
                    "could not find container with label "
                    + label
                    + " error: ",
                    e,
                )

            for blob in container.list_blobs():
                blob_name = blob.name
                blob_url = f"{base_img_url}/{label}/{blob_name}"
                url_list.append(
                    ImageUrlCreateEntry(url=blob_url, tag_ids=[tag.id])
                )

        # upload URLs in chunks of 64
        for url_chunk in self.__chunks(url_list, 64):
            upload_result = self.trainer.create_images_from_urls(
                project_id, images=url_chunk
            )
            if not upload_result.is_batch_successful:
                print("Image batch upload failed.")
                for image in upload_result.images:
                    if image.status != "OK":
                        print("Image status: ", image.status)

    def train(self, labels: list) -> None:
        """
        Trains model on all labels specified in input list, exeption is raised by self.trainer.train_projec() is asked to train on non existent labels.
        Generates unique iteration name, publishes model and sets self.iteration_name if successful.

        then publishes the model.
        C
        Parameters:
        labels (str[]): List of labels

        Returns:
        None

        #TODO return error if model is asked to train with non existent label.
        #TODO delete iterations to make sure projct never exceeds 11 iterations.
        """

        email = None

        print("Training...")
        iteration = self.trainer.train_project(
            project_id,
            reserved_budget_in_hours=1,
            notification_email_address=email,
            selected_tags=labels,
        )

        # Wait for training to complete
        while iteration.status != "Completed":
            iteration = self.trainer.get_iteration(project_id, iteration.id)
            print("Training status: " + iteration.status)
            time.sleep(1)

        # The iteration is now trained. Publish it to the project endpoint
        iteration_name = uuid.uuid4()

        self.trainer.publish_iteration(
            project_id, iteration.id, iteration_name, prediction_resource_id
        )
        self.iteration_name = iteration_name


def main():
    """
    Use main if you want to run the complete program with init, train and prediction of and example image.
    To be able to run main, make sure:
    -no more than two projects created in Azure Custom Vision
    -no more than 11 iterations done in one project

    #TODO: make method for cleaning up iterations before making a new one(max 11 iterations in Azure Custom Vision)
    """

    blob_service_client = BlobServiceClient.from_connection_string(connect_str)

    test_url = "https://originaldataset.blob.core.windows.net/ambulance/4504435055132672.png"
    labels = ["ambulance", "bench", "circle", "star", "square"]
    classifier = CVClassifier(blob_service_client)
    classifier.upload_images(labels)

    classifier.train(labels)
    result = classifier.predict(test_url)

    print(result)


if __name__ == "__main__":
    main()
