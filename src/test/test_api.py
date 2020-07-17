import os
import io
import sys
import pytest
import werkzeug
import tempfile
import datetime
from flask import json
from pytest import raises
from webapp import api
from webapp import models
from test import test_db
from test import config as cfg
from werkzeug import exceptions as excp


@pytest.fixture
def client():
    """
        Pytest fixture which configures application for testing.
    """
    api.app.config["TESTING"] = True
    with api.app.test_client() as client:
        yield client


def test_root_example(client):
    """
        Use GET request on root and check if the response is correct.
    """
    res = client.get("/")
    assert res.data == b"Yes, we're up"


def test_start_game_wrong_request(client):
    """
        Ensure that the API returns error due to unsupported request type
        (something else than GET).
    """
    # send request to test client with empty dictionary
    res = client.post("/startGame", data=dict())
    assert(b"405 Method Not Allowed" in res.data)


def test_start_game_correct(client):
    """
        Ensure that the API doesn't return error when sumitting a GET request.
    """
    res = client.get("/startGame", data=dict())
    # Ensure that the returned dictionary contains a token
    assert(b"token" in res.data)


def test_classify_wrong_request(client):
    """
        Ensure that the API returns error due to unsupported request type
        (something else than POST).
    """
    # Submit GET request
    res = client.get("/classify")
    # Should give error since POST is required
    assert(b"405 Method Not Allowed" in res.data)


def test_classify_no_image(client):
    """
        Ensure that the API returns error when there is no image submitted
        in the request.
    """
    # Since the API checks if the image is there before anything else,
    # we don't need to include anything with the request
    res = client.post("/classify", data=dict())
    # Check if the correct error code is returned
    assert b"No image submitted" in res.data


def test_classify_wrong_image(client):
    """
        Ensure that the API returns error when the image submitted in the
        request doesn't comply with the constraints checked for in the
        allowedFile function.
    """
    # Start time, token and user doesn't need to be valid, since the error is
    # supposed to be caught before these are used
    time = 0
    token, user = "", ""
    # Submit answer with the given parameters and get results
    res = classify_helper(
        client, cfg.API_PATH_DATA, cfg.API_IMAGE1, time, token, user
    )
    assert b"415 Unsupported Media Type" in res.data


def test_classify_correct(client):
    """
        Ensure that the API returns no errors when the image submitted in the
        request complies with constraints and everything seem to be good.
    """
    # Username is not unique, can therefore use the same repeatedly
    name = "testing_api"
    time = 0
    # Need to start a new game to get a token we can submit
    res1 = client.get("/startGame")
    res1 = res1.data.decode("utf-8")
    response = json.loads(res1)
    token = response["token"]
    # submit answer with parameters and retrieve results
    res = classify_helper(
        client, cfg.API_PATH_DATA, cfg.API_IMAGE4, time, token, name
    )
    # Check if the correct response data is returned
    data = json.loads(res.data.decode("utf-8"))
    assert(isinstance(data, dict))
    # Check if the correct keys are included
    assert("certainty" in data)
    assert("hasWon" in data)
    # Check if 200 is returned
    assert(res.status_code == 200)


def test_allowedFile_small_resolution():
    """
        Test if the allowedFile function within the API returns False if an
        image with too small resolution is sent as parameter.
    """
    # Test the allowedFile function with the given filename.
    # The allowedFile function should return 'false'.
    with raises(excp.UnsupportedMediaType):
        allowed_file_helper(cfg.API_IMAGE1, False, "image/png")


def test_allowedFile_too_large_file():
    """
        Test if the allowedFile function within the API returns False if an
        image above the maximum size is sent as parameter.
    """
    # Test the allowedFile function with the given filename.
    # The allowedFile function should return 'false'.
    with raises(excp.UnsupportedMediaType):
        allowed_file_helper(cfg.API_IMAGE2, False, "image/png")


def test_allowedFile_wrong_format():
    """
        Test if the allowedFile function within the API returns False if an
        image of the wrong format is sent as parameter.
    """
    # Test the allowedFile function with the given filename.
    # The allowedFile function should return 'false'.
    with raises(excp.UnsupportedMediaType):
        allowed_file_helper(cfg.API_IMAGE3, False, "image/jpeg")


def test_allowedFile_correct():
    """
        Test if the allowedFile function within the API returns True if an
        image with all constraints satisfied is sent as parameter.
    """
    # Test the allowedFile function with the given filename.
    # The allowedFile function should return 'true'.
    allowed_file_helper(cfg.API_IMAGE4, True, "image/png")


def allowed_file_helper(filename, expected_result, content_type):
    """
        Helper function for the allowedFile function tests.
    """
    # Construct path to the directory with the images
    dir_path = construct_path(cfg.API_PATH_DATA)
    # The path is only valid if the program runs from the src directory
    path = os.path.join(dir_path, filename)
    with open(path, "rb") as f:
        data_stream = f.read()
        # Create temporary file and reset seek to avoid EOF errors
        tmp = tempfile.SpooledTemporaryFile()
        tmp.write(data_stream)
        tmp.seek(0)
        # Create file storage object containing the image
        image = werkzeug.datastructures.FileStorage(stream=tmp, filename=path,
                                                    content_type=content_type)
        # Test allowedFile function with the image file
        return api.allowed_file(image)


def classify_helper(client, data_path, image, time, token, user):
    """
        Helper function which sends post request to client on /classify.
        The function returns the response given from the client

        client: client object to communicate with
        data_path: path to directory containing data
        image: name of the image in the directory given by data_path
        time: time used during game
        token: token used to validate session
        user: username of the player
    """
    # Construct path to the directory storing the test data
    dir_path = construct_path(data_path)
    path = os.path.join(dir_path, image)
    # Open image and retrieve bytes stream
    with open(path, "rb") as f:
        img_string = io.BytesIO(f.read())

    answer = {
        "image": (img_string, image),
        "token": token,
        "time": time
    }
    res = client.post(
        "/classify", content_type="multipart/form-data", data=answer)
    return res


def construct_path(dir_list):
    """
        Take in a list of directories in sequential order with regards to path
        order and construct a relative path to the last directory in the list.
    """
    # Add first element to path
    path = dir_list[0]
    # Iterate over the list (exclude 1st element)
    for elem in dir_list[1:]:
        # Append the remaining paths sequentially
        path = os.path.join(path, elem)

    return path


def test_view_highscore(client):
    """
        Test if highscore data is strucutred correctly, example of format:
        {"daily":[{"name":"mari","score":83}],
        "total":[{"name":"ole","score":105},{"name":"mari","score":83}]}
    """
    # get response
    res = client.get("/viewHighScore")
    response = json.loads(res.data)
    #check that data structure is correct
    if len(response["total"][0]) > 0:
        print("len større enn 0: ", len(response["total"][0])
        assert(isinstance(response, dict))
        assert(isinstance(response["daily"], list))
        assert(isinstance(response["total"], list))
        assert(isinstance(response["daily"][0], dict))
        assert(isinstance(response["total"][0], dict))
